#!/usr/bin/env python3
"""HASH-frame (opcode 7) over/under-read probe for the Flock mock upload server.

Tests whether the server's fixed 32-byte read for opcode 7 (HASH) correctly
respects the frame boundary, or whether extra/missing bytes desync the opcode
stream (byte smuggling into the next opcode) or hang the connection.

SANDBOX ONLY. Talks only to a local mock (upload_server.py) on localhost.
Synthetic data only — no real captures, no real tokens.
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


def _recvn(s, n):
    b = b""
    while len(b) < n:
        c = s.recv(n - len(b))
        if not c:
            raise ConnectionError("closed")
        b += c
    return b


def hello(s, token):
    payload = json.dumps({"authToken": token, "serial": "MOCK-000000", "clientVersion": "sandbox"}).encode()
    s.sendall(bytes([HELLO])); s.sendall(bytes([3]))
    s.sendall(be_long(len(payload))); s.sendall(payload)
    n = struct.unpack(">q", _recvn(s, 8))[0]
    resp = _recvn(s, n)
    s.sendall(bytes([OK]))
    return resp.decode("utf-8", "replace")


def do_preamble(s, token, data, meta):
    print("HELLO ->", hello(s, token))
    for op in (SESSION, START):
        s.sendall(bytes([op])); _recvn(s, 1)
    s.sendall(bytes([METADATA])); s.sendall(be_long(len(meta))); s.sendall(meta); _recvn(s, 1)
    s.sendall(bytes([FILE])); s.sendall(be_long(len(data)))
    s.sendall(data)
    r = _recvn(s, 1)
    print(f"   FILE ack={r[0]}")


def case_baseline(a):
    print("\n=== case: baseline (exact 32-byte HASH) ===")
    data = os.urandom(2048)
    digest = hashlib.sha256(data).digest()
    meta = json.dumps({"cameraSerial": "MOCK-000000", "createdAt": int(time.time())}).encode()
    s = connect(a.host, a.port, not a.plaintext)
    do_preamble(s, a.token, data, meta)
    s.sendall(bytes([HASH])); s.sendall(digest)
    s.settimeout(2.0)
    resp = s.recv(4)
    print(f"   sent 32B correct hash -> server responded {resp!r}")
    s.close()
    return {"case": "baseline", "sent_len": 32, "response": list(resp)}


def case_overread_smuggle(a, smuggled_opcode=SAVE):
    print(f"\n=== case: HASH over-read (33 bytes, 33rd byte = opcode {smuggled_opcode}/{NAMES.get(smuggled_opcode)}) ===")
    data = os.urandom(2048)
    digest = hashlib.sha256(data).digest()
    meta = json.dumps({"cameraSerial": "MOCK-000000", "createdAt": int(time.time())}).encode()
    s = connect(a.host, a.port, not a.plaintext)
    do_preamble(s, a.token, data, meta)
    # single sendall: 32-byte correct digest + 1 extra byte we hope gets consumed
    # as the *next* opcode by the server's main loop instead of being treated as
    # part of (or an error in) the HASH frame.
    frame = digest + bytes([smuggled_opcode])
    assert len(frame) == 33
    s.sendall(bytes([HASH]))
    s.sendall(frame)
    s.settimeout(3.0)
    # We do NOT send anything else. If the server only consumes 32 bytes for HASH
    # and then loops back to read 1 opcode byte, it will find our smuggled opcode
    # byte already sitting in the socket buffer and process it *without us sending
    # a new opcode*, producing a SECOND response byte unprompted.
    got = b""
    try:
        while len(got) < 2:
            chunk = s.recv(2 - len(got))
            if not chunk:
                break
            got += chunk
    except socket.timeout:
        pass
    print(f"   sent 33B (32B hash + smuggled opcode byte {smuggled_opcode}) -> got {len(got)} response byte(s): {list(got)}")
    smuggled = len(got) >= 2
    s.close()
    return {"case": "overread_smuggle", "sent_len": 33, "smuggled_opcode": smuggled_opcode,
            "response_bytes": list(got), "smuggling_confirmed": smuggled}


def case_underread_hang(a, hold_seconds=4.0):
    print(f"\n=== case: HASH under-read (31 bytes, then withhold 32nd byte for {hold_seconds}s) ===")
    data = os.urandom(2048)
    digest = hashlib.sha256(data).digest()
    meta = json.dumps({"cameraSerial": "MOCK-000000", "createdAt": int(time.time())}).encode()
    s = connect(a.host, a.port, not a.plaintext)
    do_preamble(s, a.token, data, meta)
    s.sendall(bytes([HASH]))
    s.sendall(digest[:31])  # one byte short
    t0 = time.time()
    s.settimeout(hold_seconds)
    hung = False
    try:
        resp = s.recv(4)
        elapsed = time.time() - t0
        print(f"   after sending 31/32 bytes, server responded {resp!r} after {elapsed:.2f}s (did NOT wait for 32nd byte)")
    except socket.timeout:
        hung = True
        elapsed = time.time() - t0
        print(f"   after sending 31/32 bytes, NO response for {elapsed:.2f}s -> server thread is blocked in recv() waiting for the missing byte (hang)")
        # now complete the frame late and confirm the server was indeed just
        # blocked waiting for exactly the missing byte (recovers once we send it)
        s.settimeout(3.0)
        s.sendall(digest[31:32])
        try:
            resp2 = s.recv(4)
            print(f"   sent missing 32nd byte late -> server responded {resp2!r} (confirms it was blocked mid-HASH-read, not crashed)")
        except socket.timeout:
            print("   sent missing 32nd byte late -> still no response (thread wedged even after completing the frame)")
    s.close()
    return {"case": "underread_hang", "sent_len": 31, "hold_seconds": hold_seconds, "hung": hung}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=18443)
    ap.add_argument("--token", default="SANDBOX-FAKE-TOKEN")
    ap.add_argument("--plaintext", action="store_true")
    ap.add_argument("--out", default=None, help="write JSON results to this path")
    a = ap.parse_args()

    results = []
    results.append(case_baseline(a))
    results.append(case_overread_smuggle(a, smuggled_opcode=SAVE))
    results.append(case_underread_hang(a, hold_seconds=4.0))

    print("\n=== summary ===")
    for r in results:
        print(r)

    if a.out:
        with open(a.out, "w") as f:
            json.dump({"target": f"{a.host}:{a.port}", "results": results}, f, indent=2)
        print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
