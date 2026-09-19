#!/usr/bin/env python3
"""State-machine-bypass ordering attack against the Flock upload mock server.

Tests whether the server enforces any protocol ordering / prerequisite steps
(HELLO before anything else, UPLOAD_START before UPLOAD_SAVE/COMPLETE, etc).
Each test case opens a FRESH connection and sends opcodes in an out-of-order
sequence that skips a normally-required predecessor step, then reports what
the server actually did (accepted/OK'd it, rejected it, closed the connection,
hung, or crashed).

SANDBOX ONLY - synthetic data, localhost only. Companion to upload_client.py.
"""
import argparse, hashlib, json, socket, ssl, struct, sys, time

OK, HELLO, PROTO, SESSION, START, FILE, HASH, SAVE, COMPLETE, METADATA = 1, 2, 3, 4, 5, 6, 7, 8, 9, 12
NAMES = {1: "OK", 2: "HELLO", 3: "PROTO", 4: "SESSION", 5: "UPLOAD_START", 6: "FILE",
         7: "HASH", 8: "UPLOAD_SAVE", 9: "UPLOAD_COMPLETE", 12: "METADATA"}


def connect(host, port, tls, timeout=5):
    s = socket.create_connection((host, port), timeout=timeout)
    if tls:
        ctx = ssl._create_unverified_context()
        s = ctx.wrap_socket(s, server_hostname=host)
    s.settimeout(timeout)
    return s


def be_long(n):
    return struct.pack(">q", n)


def try_read(s, n, timeout=2.0):
    """Best-effort read of up to n bytes within timeout. Returns (bytes, error|None)."""
    s.settimeout(timeout)
    try:
        b = s.recv(n)
        return b, None
    except socket.timeout:
        return b"", "TIMEOUT(no response - possible hang)"
    except (ConnectionError, OSError) as e:
        return b"", f"{type(e).__name__}: {e}"


def send_metadata_no_hello(host, port, tls):
    """Send METADATA as the very first opcode, before HELLO/auth."""
    s = connect(host, port, tls)
    meta = json.dumps({"cameraSerial": "MOCK-ATTACK", "createdAt": int(time.time()),
                        "note": "ordering-attack: metadata sent pre-auth"}).encode()
    s.sendall(bytes([METADATA]))
    s.sendall(be_long(len(meta)))
    s.sendall(meta)
    resp, err = try_read(s, 16)
    s.close()
    return {"case": "METADATA_before_HELLO", "sent_bytes": len(meta), "resp": resp.hex() if resp else None, "error": err}


def send_file_no_hello(host, port, tls):
    """Send FILE contents as the first opcode, before HELLO/SESSION/UPLOAD_START."""
    s = connect(host, port, tls)
    data = b"\x41" * 4096  # synthetic
    s.sendall(bytes([FILE]))
    s.sendall(be_long(len(data)))
    s.sendall(data)
    resp, err = try_read(s, 16)
    s.close()
    return {"case": "FILE_before_HELLO", "sent_bytes": len(data), "resp": resp.hex() if resp else None, "error": err}


def send_hash_no_file(host, port, tls):
    """Send HASH as the first opcode, with no prior FILE upload -> hash of empty digest."""
    s = connect(host, port, tls)
    fake_digest = hashlib.sha256(b"").digest()
    s.sendall(bytes([HASH]))
    s.sendall(fake_digest)
    resp, err = try_read(s, 16)
    s.close()
    return {"case": "HASH_before_FILE_no_HELLO", "sent_digest": fake_digest.hex(), "resp": resp.hex() if resp else None, "error": err}


def send_save_complete_no_start(host, port, tls):
    """Send UPLOAD_SAVE then UPLOAD_COMPLETE with no preceding HELLO/SESSION/UPLOAD_START/FILE/HASH."""
    s = connect(host, port, tls)
    results = []
    for op in (SAVE, COMPLETE):
        s.sendall(bytes([op]))
        resp, err = try_read(s, 16)
        results.append({"opcode": NAMES[op], "resp": resp.hex() if resp else None, "error": err})
    s.close()
    return {"case": "UPLOAD_SAVE_and_COMPLETE_no_START", "steps": results}


def send_full_reverse_order(host, port, tls):
    """Send the entire normal sequence in REVERSE opcode order on one connection,
    with no HELLO at all, to see if the server just blindly acks every opcode
    regardless of what came before (confirming no state machine at all)."""
    s = connect(host, port, tls)
    order = [COMPLETE, SAVE, HASH, FILE, METADATA, START, SESSION]
    results = []
    for op in order:
        s.sendall(bytes([op]))
        if op == FILE:
            data = b"\x42" * 512
            s.sendall(be_long(len(data)))
            s.sendall(data)
        elif op == HASH:
            s.sendall(hashlib.sha256(b"").digest())
        elif op == METADATA:
            meta = b'{"reverse":"order-attack"}'
            s.sendall(be_long(len(meta)))
            s.sendall(meta)
        resp, err = try_read(s, 16)
        results.append({"opcode": NAMES[op], "resp": resp.hex() if resp else None, "error": err})
        if err and "TIMEOUT" not in err:
            break
    s.close()
    return {"case": "FULL_SEQUENCE_REVERSE_ORDER_no_HELLO", "steps": results}


def send_upload_save_then_file_then_hash_mismatched(host, port, tls):
    """Interleave: UPLOAD_SAVE + UPLOAD_COMPLETE BEFORE sending the file/hash at all,
    then send file/hash AFTER completion was already acked, on the same connection,
    to see if the server accepts a 'completed' upload with nothing behind it, and
    whether it still happily processes file data delivered afterward."""
    s = connect(host, port, tls)
    results = []
    for op in (SAVE, COMPLETE):
        s.sendall(bytes([op]))
        resp, err = try_read(s, 16)
        results.append({"phase": "pre", "opcode": NAMES[op], "resp": resp.hex() if resp else None, "error": err})
    data = b"\x43" * 2048
    s.sendall(bytes([FILE]))
    s.sendall(be_long(len(data)))
    s.sendall(data)
    resp, err = try_read(s, 16)
    results.append({"phase": "post-complete", "opcode": "FILE", "resp": resp.hex() if resp else None, "error": err})
    s.close()
    return {"case": "SAVE_COMPLETE_before_FILE_then_FILE_after", "steps": results}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8443)
    ap.add_argument("--plaintext", action="store_true")
    ap.add_argument("--out", default=None, help="write JSON results to this file")
    a = ap.parse_args()
    tls = not a.plaintext

    cases = [
        send_metadata_no_hello,
        send_file_no_hello,
        send_hash_no_file,
        send_save_complete_no_start,
        send_full_reverse_order,
        send_upload_save_then_file_then_hash_mismatched,
    ]

    all_results = []
    for fn in cases:
        t0 = time.time()
        try:
            r = fn(a.host, a.port, tls)
            r["wall_time_s"] = round(time.time() - t0, 3)
            r["status"] = "completed"
        except Exception as e:
            r = {"case": fn.__name__, "status": "EXCEPTION", "error": f"{type(e).__name__}: {e}",
                 "wall_time_s": round(time.time() - t0, 3)}
        print(json.dumps(r, indent=2))
        all_results.append(r)

    if a.out:
        with open(a.out, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"\nwrote {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
