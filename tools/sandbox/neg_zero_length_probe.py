#!/usr/bin/env python3
"""Adversarial length-prefix probe: negative / zero-value 8-byte BE length prefixes.

Distinct from the existing 'giant-length' (2**60) and 'negative-length' (-1 on FILE)
cases in upload_client.py's fuzz(). This probes:
  - INT64_MIN (0x8000000000000000, i.e. -2**63) as the length prefix
  - exactly 0 as the length prefix
  - -1 (for completeness / cross-check against the existing FILE-only case)
against THREE different opcodes that all read an 8-byte BE length first:
  HELLO (2), METADATA (12), FILE (6)

Goal: see whether the mock server's `read_len()` (struct.unpack(">q", ...)) plus the
subsequent `recvn(f, n)` / `remaining -= len(chunk)` loop mishandles a negative or
zero n -- e.g. Python's recvn with negative n calls conn.recv(negative) which raises
ValueError (crashing the handler thread), or n==0 which should just be a legitimate
empty read (should be handled fine), vs some other divergent behavior.

SANDBOX ONLY -- connects only to a local mock server instance (127.0.0.1) started
from tools/sandbox/upload_server.py in this same environment.
"""
import argparse
import json
import socket
import ssl
import struct
import time

HELLO, METADATA, FILE, OK = 2, 12, 6, 1

LENGTH_CASES = [
    ("zero", 0),
    ("neg-one", -1),
    ("int64-min", -(2**63)),  # 0x8000000000000000 two's complement
    ("neg-large", -(2**40)),
]


def connect(host, port, tls):
    s = socket.create_connection((host, port), timeout=8)
    if tls:
        ctx = ssl._create_unverified_context()
        s = ctx.wrap_socket(s, server_hostname=host)
    return s


def be_long(n):
    # struct.pack(">q", n) requires -2**63 <= n < 2**63; matches Java's signed long
    return struct.pack(">q", n)


def recv_nonblocking(s, n=64, timeout=1.5):
    s.settimeout(timeout)
    try:
        return s.recv(n)
    except Exception:
        return b""


def probe_hello(host, port, tls, length_name, length_val, log):
    """Send opcode HELLO, protocol byte 3, then the crafted length, then a short body."""
    t0 = time.time()
    try:
        s = connect(host, port, tls)
        s.sendall(bytes([HELLO]))
        s.sendall(bytes([3]))  # protocol version
        s.sendall(be_long(length_val))
        # send a small real-looking body regardless of declared length; if server
        # tries to recv(length_val) with a huge/negative value we want to see what
        # happens without needing to actually own petabytes of data.
        body = json.dumps({"authToken": "SANDBOX-FAKE-TOKEN", "serial": "MOCK-000000"}).encode()
        s.sendall(body)
        resp = recv_nonblocking(s, 256, 2.0)
        dt = time.time() - t0
        log(f"HELLO   len={length_name:10} raw={length_val:>22} -> resp={resp!r} elapsed={dt:.2f}s")
        s.close()
        return {"opcode": "HELLO", "length_case": length_name, "length_value": length_val,
                "response": repr(resp), "elapsed_s": dt, "outcome": "responded" if resp else "no-response/timeout"}
    except Exception as e:
        dt = time.time() - t0
        log(f"HELLO   len={length_name:10} raw={length_val:>22} -> EXCEPTION {type(e).__name__}: {e} elapsed={dt:.2f}s")
        return {"opcode": "HELLO", "length_case": length_name, "length_value": length_val,
                "exception": f"{type(e).__name__}: {e}", "elapsed_s": dt, "outcome": "client-exception"}


def probe_metadata(host, port, tls, length_name, length_val, log):
    t0 = time.time()
    try:
        s = connect(host, port, tls)
        # do a real HELLO first so the server is in a sane per-connection state
        s.sendall(bytes([HELLO])); s.sendall(bytes([3]))
        hello_body = json.dumps({"authToken": "SANDBOX-FAKE-TOKEN", "serial": "MOCK-000000"}).encode()
        s.sendall(be_long(len(hello_body))); s.sendall(hello_body)
        n = struct.unpack(">q", _recvn_fixed(s, 8))[0]
        _recvn_fixed(s, n)
        s.sendall(bytes([OK]))

        # now the crafted METADATA frame
        s.sendall(bytes([METADATA]))
        s.sendall(be_long(length_val))
        body = b'{"probe":"negzero-metadata"}'
        s.sendall(body)
        resp = recv_nonblocking(s, 256, 2.0)
        dt = time.time() - t0
        log(f"METADATA len={length_name:10} raw={length_val:>22} -> resp={resp!r} elapsed={dt:.2f}s")
        s.close()
        return {"opcode": "METADATA", "length_case": length_name, "length_value": length_val,
                "response": repr(resp), "elapsed_s": dt, "outcome": "responded" if resp else "no-response/timeout"}
    except Exception as e:
        dt = time.time() - t0
        log(f"METADATA len={length_name:10} raw={length_val:>22} -> EXCEPTION {type(e).__name__}: {e} elapsed={dt:.2f}s")
        return {"opcode": "METADATA", "length_case": length_name, "length_value": length_val,
                "exception": f"{type(e).__name__}: {e}", "elapsed_s": dt, "outcome": "client-exception"}


def probe_file(host, port, tls, length_name, length_val, log):
    t0 = time.time()
    try:
        s = connect(host, port, tls)
        s.sendall(bytes([HELLO])); s.sendall(bytes([3]))
        hello_body = json.dumps({"authToken": "SANDBOX-FAKE-TOKEN", "serial": "MOCK-000000"}).encode()
        s.sendall(be_long(len(hello_body))); s.sendall(hello_body)
        n = struct.unpack(">q", _recvn_fixed(s, 8))[0]
        _recvn_fixed(s, n)
        s.sendall(bytes([OK]))

        # now the crafted FILE frame
        s.sendall(bytes([FILE]))
        s.sendall(be_long(length_val))
        # send a small chunk of "file data" regardless
        s.sendall(b"\x00" * 16)
        resp = recv_nonblocking(s, 256, 2.0)
        dt = time.time() - t0
        log(f"FILE    len={length_name:10} raw={length_val:>22} -> resp={resp!r} elapsed={dt:.2f}s")
        s.close()
        return {"opcode": "FILE", "length_case": length_name, "length_value": length_val,
                "response": repr(resp), "elapsed_s": dt, "outcome": "responded" if resp else "no-response/timeout"}
    except Exception as e:
        dt = time.time() - t0
        log(f"FILE    len={length_name:10} raw={length_val:>22} -> EXCEPTION {type(e).__name__}: {e} elapsed={dt:.2f}s")
        return {"opcode": "FILE", "length_case": length_name, "length_value": length_val,
                "exception": f"{type(e).__name__}: {e}", "elapsed_s": dt, "outcome": "client-exception"}


def _recvn_fixed(s, n):
    b = b""
    while len(b) < n:
        c = s.recv(n - len(b))
        if not c:
            raise ConnectionError("closed")
        b += c
    return b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8443)
    ap.add_argument("--plaintext", action="store_true")
    ap.add_argument("--out", default=None, help="write JSON results to this path")
    a = ap.parse_args()

    results = []
    def log(*args_):
        print(*args_, flush=True)

    log(f"=== negative/zero length-prefix probe against {a.host}:{a.port} ===")
    for name, val in LENGTH_CASES:
        results.append(probe_hello(a.host, a.port, not a.plaintext, name, val, log))
    for name, val in LENGTH_CASES:
        results.append(probe_metadata(a.host, a.port, not a.plaintext, name, val, log))
    for name, val in LENGTH_CASES:
        results.append(probe_file(a.host, a.port, not a.plaintext, name, val, log))

    # sanity check: is the server still alive/responsive after all that?
    try:
        s = connect(a.host, a.port, not a.plaintext)
        s.sendall(bytes([HELLO])); s.sendall(bytes([3]))
        body = json.dumps({"authToken": "SANDBOX-FAKE-TOKEN", "serial": "POST-PROBE-CHECK"}).encode()
        s.sendall(be_long(len(body))); s.sendall(body)
        n = struct.unpack(">q", _recvn_fixed(s, 8))[0]
        resp = _recvn_fixed(s, n)
        log(f"post-probe liveness check: server responded normally, resp={resp!r}")
        results.append({"check": "post-probe-liveness", "outcome": "server-alive", "response": repr(resp)})
        s.close()
    except Exception as e:
        log(f"post-probe liveness check: FAILED -- {type(e).__name__}: {e}")
        results.append({"check": "post-probe-liveness", "outcome": "server-unresponsive",
                         "exception": f"{type(e).__name__}: {e}"})

    if a.out:
        with open(a.out, "w") as f:
            json.dump(results, f, indent=2)
        log(f"wrote {a.out}")


if __name__ == "__main__":
    main()
