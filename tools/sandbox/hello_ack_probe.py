#!/usr/bin/env python3
"""Adversarial probe: unvalidated HELLO client-ack byte.

IDEA UNDER TEST (source: protocol):
  After HELLO, the client is expected to send a single "ack" byte (OK=1) back to the
  server before continuing. Does the server actually validate that byte's VALUE? If not,
  can sending an arbitrary byte there (a) still let the session proceed normally, or
  (b) get misinterpreted -- e.g. because the byte happens to equal another opcode's value,
  does the server end up dispatching it as an opcode instead of just consuming it as an
  (unchecked) ack, i.e. "opcode smuggling" at the HELLO boundary?

This is a pure protocol-logic probe against our OWN local sandbox mock
(upload_server.py in this same directory). Synthetic data only; localhost only.

Usage:
  python3 hello_ack_probe.py --port 8543 --ack 0            # ack = 0x00
  python3 hello_ack_probe.py --port 8543 --ack 12           # ack = METADATA opcode value
  python3 hello_ack_probe.py --port 8543 --ack 4            # ack = SESSION opcode value
"""
import argparse, hashlib, json, os, socket, ssl, struct, sys, time

OK, HELLO, PROTO, SESSION, START, FILE, HASH, SAVE, COMPLETE, METADATA = 1, 2, 3, 4, 5, 6, 7, 8, 9, 12
NAMES = {1: "OK", 2: "HELLO", 3: "PROTO", 4: "SESSION", 5: "UPLOAD_START", 6: "FILE",
         7: "HASH", 8: "UPLOAD_SAVE", 9: "UPLOAD_COMPLETE", 12: "METADATA"}


def connect(host, port, tls):
    s = socket.create_connection((host, port), timeout=10)
    if tls:
        ctx = ssl._create_unverified_context()
        s = ctx.wrap_socket(s, server_hostname=host)
    return s


def be_long(n):
    return struct.pack(">q", n)


def recvn(s, n):
    b = b""
    while len(b) < n:
        c = s.recv(n - len(b))
        if not c:
            raise ConnectionError("closed")
        b += c
    return b


def try_recv_nonblocking(s, n, timeout=1.0):
    s.settimeout(timeout)
    try:
        return s.recv(n)
    except socket.timeout:
        return None
    finally:
        s.settimeout(10)


def hello_with_bad_ack(s, token, ack_byte, log):
    payload = json.dumps({"authToken": token, "serial": "MOCK-000000",
                           "clientVersion": "sandbox-ack-probe"}).encode()
    s.sendall(bytes([HELLO]))
    s.sendall(bytes([3]))  # protocol version marker
    s.sendall(be_long(len(payload)))
    s.sendall(payload)
    n = struct.unpack(">q", recvn(s, 8))[0]
    resp = recvn(s, n).decode("utf-8", "replace")
    log(f"server HELLO response: {resp}")
    # THE PROBE: send an arbitrary byte instead of the expected OK(1) ack.
    log(f"sending BOGUS client-ack byte = {ack_byte} (valid/expected value is {OK}=OK)")
    s.sendall(bytes([ack_byte & 0xFF]))
    return resp


def run_probe(a):
    log = lambda *m: print("[probe]", *m, flush=True)
    s = connect(a.host, a.port, not a.plaintext)
    hello_with_bad_ack(s, a.token, a.ack, log)

    # Does the connection still work after a bad ack? Continue the normal protocol flow
    # (SESSION -> UPLOAD_START -> METADATA -> FILE -> HASH -> SAVE/COMPLETE) and see
    # whether the server is still in a sane state, desynced, or has treated our "ack"
    # byte as a smuggled opcode (which would show up as an extra/missing OK reply,
    # a hang, or a reply mismatched to the wrong step).
    results = []

    def step(label, send_bytes):
        s.sendall(send_bytes)
        r = try_recv_nonblocking(s, 16, timeout=2.0)
        results.append((label, r))
        log(f"step {label}: sent {send_bytes!r} -> reply {r!r}")

    step("SESSION", bytes([SESSION]))
    step("UPLOAD_START", bytes([START]))

    meta = json.dumps({"cameraSerial": "MOCK-000000", "createdAt": int(time.time()),
                        "detections": []}).encode()
    step("METADATA", bytes([METADATA]) + be_long(len(meta)) + meta)

    data = os.urandom(2048)
    digest = hashlib.sha256(data).digest()
    s.sendall(bytes([FILE]) + be_long(len(data)))
    s.sendall(data)
    r = try_recv_nonblocking(s, 16, timeout=2.0)
    results.append(("FILE", r))
    log(f"step FILE: sent {len(data)}B synthetic -> reply {r!r}")

    step("HASH", bytes([HASH]) + digest)
    hash_ok = results[-1][1] == bytes([OK])

    step("UPLOAD_SAVE", bytes([SAVE]))
    step("UPLOAD_COMPLETE", bytes([COMPLETE]))

    s.close()

    print()
    print("=== SUMMARY ===")
    print(f"bogus ack byte sent: {a.ack}")
    print(f"hash verified by server after bogus ack + full flow: {hash_ok}")
    for label, r in results:
        print(f"  {label:16} -> {r!r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8543)
    ap.add_argument("--token", default="SANDBOX-FAKE-TOKEN")
    ap.add_argument("--plaintext", action="store_true")
    ap.add_argument("--ack", type=int, default=0, help="bogus ack byte value to send instead of OK(1)")
    a = ap.parse_args()
    run_probe(a)


if __name__ == "__main__":
    main()
