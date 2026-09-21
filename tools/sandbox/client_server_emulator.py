#!/usr/bin/env python3
"""Controllable localhost emulator for exercising upload_client.py behavior.

The emulator accepts the same opcodes as upload_server.py but allows deterministic
fault injection in server responses so we can fuzz client request/response
handling and state-transition behavior.
"""
from __future__ import annotations

import argparse
import json
import socket
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

OK, FAIL, HELLO, SESSION, START, FILE, HASH, SAVE, COMPLETE, METADATA = 1, 0, 2, 4, 5, 6, 7, 8, 9, 12
CANONICAL_FLOW = [HELLO, SESSION, START, METADATA, FILE, HASH, SAVE, COMPLETE, SESSION]
OP_NAME = {
    OK: "OK",
    FAIL: "FAIL",
    HELLO: "HELLO",
    SESSION: "SESSION",
    START: "UPLOAD_START",
    FILE: "FILE",
    HASH: "HASH",
    SAVE: "UPLOAD_SAVE",
    COMPLETE: "UPLOAD_COMPLETE",
    METADATA: "METADATA",
}


@dataclass(frozen=True)
class Scenario:
    name: str
    hello_mode: str = "ok"  # ok | truncated | close
    fail_acks: tuple[int, ...] = ()
    strict_flow: bool = True
    close_after_fail: bool = False


SCENARIOS: dict[str, Scenario] = {
    "happy-path": Scenario(name="happy-path"),
    "hello-truncated-response": Scenario(name="hello-truncated-response", hello_mode="truncated"),
    "hello-close-no-response": Scenario(name="hello-close-no-response", hello_mode="close"),
    "metadata-fail-ack": Scenario(name="metadata-fail-ack", fail_acks=(METADATA,)),
    "hash-fail-ack": Scenario(name="hash-fail-ack", fail_acks=(HASH,)),
    "session-close-fail": Scenario(name="session-close-fail", fail_acks=(SESSION,), close_after_fail=True),
}


def recvn(conn: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("peer closed")
        buf += chunk
    return buf


def read_len(conn: socket.socket) -> int:
    return struct.unpack(">q", recvn(conn, 8))[0]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _record_event(events: list[dict[str, Any]], **kwargs: Any) -> None:
    evt = {"ts": round(time.time(), 3)}
    evt.update(kwargs)
    events.append(evt)


def _handle_hello(conn: socket.socket, scenario: Scenario, events: list[dict[str, Any]]) -> bool:
    proto = recvn(conn, 1)[0]
    hello_len = read_len(conn)
    payload = recvn(conn, hello_len)
    _record_event(events, kind="hello", proto=proto, payload_len=len(payload))
    if scenario.hello_mode == "close":
        _record_event(events, kind="hello-response", mode="close-without-response")
        return False
    if scenario.hello_mode == "truncated":
        resp = b'{"status":"ok","mock":true}'
        conn.sendall(struct.pack(">q", len(resp) + 5) + resp)
        _record_event(events, kind="hello-response", mode="truncated", declared_len=len(resp) + 5, sent_len=len(resp))
        return False
    resp = b'{"status":"ok","mock":true}'
    conn.sendall(struct.pack(">q", len(resp)) + resp)
    ack = recvn(conn, 1)[0]
    _record_event(events, kind="hello-response", mode="ok", client_ack=ack)
    return True


def _read_frame_payload(conn: socket.socket, op: int) -> dict[str, Any]:
    if op == METADATA:
        n = read_len(conn)
        recvn(conn, n)
        return {"declared_len": n}
    if op == FILE:
        n = read_len(conn)
        recvn(conn, n)
        return {"declared_len": n}
    if op == HASH:
        digest = recvn(conn, 32)
        return {"hash_prefix": digest.hex()[:16]}
    return {}


def run_server(args: argparse.Namespace) -> int:
    scenario = SCENARIOS[args.scenario]
    events: list[dict[str, Any]] = []
    received_ops: list[int] = []
    failures = 0
    expected_idx = 0
    session_complete = False
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((args.host, args.port))
    srv.listen(1)
    bound_port = srv.getsockname()[1]
    print(f"emulator-listening:{bound_port}", flush=True)
    try:
        conn, addr = srv.accept()
    except OSError as exc:
        _write_json(Path(args.report), {"scenario": scenario.name, "error": str(exc)})
        return 1
    conn.settimeout(args.timeout)
    _record_event(events, kind="accept", peer=f"{addr[0]}:{addr[1]}")
    try:
        first = recvn(conn, 1)[0]
        received_ops.append(first)
        if first != HELLO:
            _record_event(events, kind="protocol-error", detail=f"first opcode {first} != HELLO")
            conn.sendall(bytes([FAIL]))
            failures += 1
        elif not _handle_hello(conn, scenario, events):
            pass
        else:
            expected_idx = 1
            while True:
                op_b = conn.recv(1)
                if not op_b:
                    break
                op = op_b[0]
                received_ops.append(op)
                payload_info = _read_frame_payload(conn, op)
                flow_ok = True
                if scenario.strict_flow and expected_idx < len(CANONICAL_FLOW):
                    expected_op = CANONICAL_FLOW[expected_idx]
                    if op != expected_op:
                        flow_ok = False
                        failures += 1
                        _record_event(
                            events,
                            kind="state-mismatch",
                            expected=OP_NAME.get(expected_op, str(expected_op)),
                            got=OP_NAME.get(op, str(op)),
                        )
                if flow_ok and expected_idx < len(CANONICAL_FLOW):
                    expected_idx += 1
                ack = FAIL if (op in scenario.fail_acks or not flow_ok) else OK
                if ack == FAIL:
                    failures += 1
                conn.sendall(bytes([ack]))
                _record_event(
                    events,
                    kind="opcode",
                    opcode=op,
                    opcode_name=OP_NAME.get(op, f"UNKNOWN_{op}"),
                    ack=ack,
                    **payload_info,
                )
                if op == SESSION and expected_idx >= len(CANONICAL_FLOW):
                    session_complete = True
                if ack == FAIL and scenario.close_after_fail:
                    break
    except (ConnectionError, OSError, struct.error, socket.timeout) as exc:
        _record_event(events, kind="connection-error", detail=f"{type(exc).__name__}: {exc}")
    finally:
        try:
            conn.close()
        except Exception:
            pass
        srv.close()

    _write_json(
        Path(args.report),
        {
            "scenario": scenario.name,
            "received_ops": [OP_NAME.get(x, str(x)) for x in received_ops],
            "session_complete": session_complete,
            "failures": failures,
            "events": events,
        },
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0, help="0 = auto-assign ephemeral port")
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--scenario", choices=sorted(SCENARIOS.keys()), required=True)
    parser.add_argument("--report", required=True, help="Path to write JSON report")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return run_server(args)


if __name__ == "__main__":
    raise SystemExit(main())
