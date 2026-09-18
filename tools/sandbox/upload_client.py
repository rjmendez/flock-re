#!/usr/bin/env python3
"""Client/attacker for the Flock capture-upload protocol (see upload_server.py).

Speaks the reversed wire protocol so you can (a) replay a realistic capture upload
against the mock and confirm the round-trip, and (b) send malformed frames to probe
the server's parser (fuzz mode). Reconstructed from `ConnectionClient`.

SANDBOX ONLY — connect only to your own mock server on localhost.
"""
import argparse, hashlib, json, os, socket, ssl, struct, sys, time

OK, HELLO, PROTO, SESSION, START, FILE, HASH, SAVE, COMPLETE, METADATA = 1,2,3,4,5,6,7,8,9,12


def connect(host, port, tls):
    s = socket.create_connection((host, port), timeout=10)
    if tls:
        ctx = ssl._create_unverified_context()  # mirrors the device: no cert pinning
        s = ctx.wrap_socket(s, server_hostname=host)
    return s


def be_long(n):
    return struct.pack(">q", n)


def hello(s, token):
    payload = json.dumps({"authToken": token, "serial": "MOCK-000000", "clientVersion": "sandbox"}).encode()
    s.sendall(bytes([HELLO])); s.sendall(bytes([PROTO, 3]) if False else bytes([3]))
    s.sendall(be_long(len(payload))); s.sendall(payload)
    n = struct.unpack(">q", _recvn(s, 8))[0]
    resp = _recvn(s, n)
    _recvn_opt(s)  # server may not push more
    s.sendall(bytes([OK]))
    return resp.decode("utf-8", "replace")


def _recvn(s, n):
    b = b""
    while len(b) < n:
        c = s.recv(n - len(b))
        if not c:
            raise ConnectionError("closed")
        b += c
    return b


def _recvn_opt(s):
    s.settimeout(0.3)
    try:
        return s.recv(1)
    except Exception:
        return b""
    finally:
        s.settimeout(10)


def normal_upload(a):
    data = os.urandom(a.size)  # synthetic media, never a real capture
    digest = hashlib.sha256(data).digest()
    meta = json.dumps({"cameraSerial": "MOCK-000000", "createdAt": int(time.time()),
                       "detections": [{"className": "vehicle", "confidence": 0.9,
                                       "xmin": 0.1, "ymin": 0.1, "xmax": 0.5, "ymax": 0.5}]}).encode()
    s = connect(a.host, a.port, not a.plaintext)
    print("HELLO ->", hello(s, a.token))
    for op in (SESSION, START):
        s.sendall(bytes([op])); _recvn(s, 1)
    s.sendall(bytes([METADATA])); s.sendall(be_long(len(meta))); s.sendall(meta); _recvn(s, 1)
    s.sendall(bytes([FILE])); s.sendall(be_long(len(data)))
    for i in range(0, len(data), a.chunk):
        s.sendall(data[i:i + a.chunk])
    _recvn(s, 1)
    s.sendall(bytes([HASH])); s.sendall(digest)
    hres = _recvn(s, 1)[0]
    print(f"HASH match on server = {hres == OK} (sent {len(data)}B, sha256={digest.hex()[:16]}...)")
    for op in (SAVE, COMPLETE, SESSION):
        s.sendall(bytes([op])); _recvn(s, 1)
    s.close()
    print("upload round-trip OK")


def fuzz(a):
    import random
    random.seed(a.seed)
    cases = [
        ("giant-length", lambda s: (s.sendall(bytes([METADATA])), s.sendall(be_long(2**60)), s.sendall(b"x"))),
        ("negative-length", lambda s: (s.sendall(bytes([FILE])), s.sendall(struct.pack(">q", -1)))),
        ("truncated-hash", lambda s: (s.sendall(bytes([HASH])), s.sendall(b"\x00" * 4))),
        ("unknown-opcode", lambda s: s.sendall(bytes([200]))),
        ("length-body-mismatch", lambda s: (s.sendall(bytes([METADATA])), s.sendall(be_long(1000)), s.sendall(b"short"))),
    ]
    for name, fn in cases:
        try:
            s = connect(a.host, a.port, not a.plaintext)
            hello(s, a.token)
            fn(s)
            s.settimeout(1.5)
            resp = s.recv(16)
            print(f"[fuzz] {name:22} -> server responded {resp!r} (survived)")
            s.close()
        except Exception as e:
            print(f"[fuzz] {name:22} -> {type(e).__name__}: {e}")
    print("fuzz pass complete — inspect server logs for crashes/hangs/oversized allocations")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8443)
    ap.add_argument("--token", default="SANDBOX-FAKE-TOKEN", help="fake token; never a real one")
    ap.add_argument("--size", type=int, default=12000, help="synthetic media size (bytes)")
    ap.add_argument("--chunk", type=int, default=2800)
    ap.add_argument("--plaintext", action="store_true")
    ap.add_argument("--fuzz", action="store_true")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    (fuzz if a.fuzz else normal_upload)(a)


if __name__ == "__main__":
    main()
