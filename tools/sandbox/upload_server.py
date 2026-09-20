#!/usr/bin/env python3
"""Mock of the Flock capture-upload server (the raw-TLS binary protocol).

Reconstructed from flock-st-germain `ConnectionClient` (static analysis of the public
leak). It lets you run the *device's* upload client against a LOCAL server so you can
see exactly what a camera transmits (the "debug-level data": auth token, per-capture
metadata JSON, the media file, the SHA-256), and it is a target you can attack/fuzz.

WIRE FORMAT (single-byte opcodes; 8-byte BIG-ENDIAN length prefixes; SHA-256):
  1  OK/ack            2  HELLO            3  protocol-version marker
  4  SESSION start/end 5  UPLOAD_START     6  FILE contents (len + chunks<=2800B)
  7  HASH (32 bytes)   8  UPLOAD_SAVE      9  UPLOAD_COMPLETE      12 METADATA
HELLO: client sends 2,3,<8-byte len><hello-json (carries auth token)>, reads
<8-byte len><server json>, sends 1. Server replies to each later op with one OK byte.

SANDBOX ONLY. Never point a real device at a real Flock host; never use a real token
against a real endpoint. This talks only to your own client on localhost.
"""
import argparse, hashlib, json, socket, ssl, struct, sys, threading, time

OK, FAIL, HELLO, PROTO, SESSION, START, FILE, HASH, SAVE, COMPLETE, METADATA = 1,0,2,3,4,5,6,7,8,9,12
MAX_FRAME_BYTES = 1 << 20
NAMES = {1:"OK", 0:"FAIL", 2:"HELLO", 3:"PROTO", 4:"SESSION", 5:"UPLOAD_START", 6:"FILE", 7:"HASH", 8:"UPLOAD_SAVE", 9:"UPLOAD_COMPLETE", 12:"METADATA"}


def recvn(f, n):
    b = b""
    while len(b) < n:
        c = f.recv(n - len(b))
        if not c:
            raise ConnectionError("peer closed")
        b += c
    return b


def read_len(f, *, max_bytes=MAX_FRAME_BYTES):
    n = struct.unpack(">q", recvn(f, 8))[0]
    if n <= 0 or n > max_bytes:
        raise ValueError(f"length prefix out of range: {n} (max={max_bytes})")
    return n


def fail_closed(conn, log, reason):
    log(f"   {reason}")
    try:
        conn.sendall(bytes([FAIL]))
    except OSError:
        pass
    raise ConnectionError(reason)


def handle(conn, addr, args):

    log = lambda *a: print(f"[{addr[1]}]", *a, flush=True)
    received_file = hashlib.sha256()
    file_bytes = 0
    try:
        while True:
            op_b = conn.recv(1)
            if not op_b:
                log("connection closed"); return
            op = op_b[0]
            log(f"<- opcode {op} ({NAMES.get(op,'?')})")
            if op == HELLO:
                try:
                    proto = recvn(conn, 1)[0]
                    n = read_len(conn)
                    payload = recvn(conn, n).decode("utf-8", "replace")
                except (ConnectionError, ValueError, struct.error) as exc:
                    fail_closed(conn, log, f"invalid HELLO payload: {exc}")
                log(f"   protocol=v{proto}  hello-payload ({n}B): {payload[:400]}")
                # NOTE: the hello payload carries the per-device auth token — captured here,
                # never validated against anything (sandbox).
                resp = json.dumps({"status": "ok", "mock": True}).encode()
                conn.sendall(struct.pack(">q", len(resp)) + resp)
                ack = recvn(conn, 1)[0]
                log(f"   client ack={ack}")
            elif op == METADATA:
                try:
                    n = read_len(conn)
                    meta = recvn(conn, n).decode("utf-8", "replace")
                except (ConnectionError, ValueError, struct.error) as exc:
                    fail_closed(conn, log, f"invalid METADATA length: {exc}")
                log(f"   METADATA ({n}B): {meta[:600]}")
                conn.sendall(bytes([OK]))
            elif op == FILE:
                try:
                    total = read_len(conn)
                except (ConnectionError, ValueError, struct.error) as exc:
                    fail_closed(conn, log, f"invalid FILE length: {exc}")
                log(f"   FILE declared {total}B; reading in <= {args.chunk}B chunks")
                remaining = total
                while remaining > 0:
                    chunk = conn.recv(min(args.chunk, remaining))
                    if not chunk:
                        break
                    received_file.update(chunk); file_bytes += len(chunk); remaining -= len(chunk)
                log(f"   received {file_bytes}B, sha256={received_file.hexdigest()}")
                conn.sendall(bytes([OK]))
            elif op == HASH:
                try:
                    client_hash = recvn(conn, 32)
                except ConnectionError as exc:
                    fail_closed(conn, log, f"truncated HASH frame: {exc}")
                ours = received_file.digest()
                match = client_hash == ours
                log(f"   client sha256={client_hash.hex()}  match={match}")
                conn.sendall(bytes([OK if match else FAIL]))
            elif op in (SESSION, START, SAVE, COMPLETE, PROTO):
                conn.sendall(bytes([OK]))
            else:
                log(f"   !! unknown opcode {op} — failing closed; no success ack is sent")
                conn.sendall(bytes([FAIL]))
                return
    except (ConnectionError, ssl.SSLError, struct.error) as e:
        log(f"   session ended: {e}")
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8443)
    ap.add_argument("--cert", default="server.pem", help="TLS cert+key (see gen_cert.sh); omit with --plaintext")
    ap.add_argument("--plaintext", action="store_true", help="run without TLS (protocol testing)")
    ap.add_argument("--chunk", type=int, default=2800)
    a = ap.parse_args()

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((a.host, a.port)); srv.listen(5)
    ctx = None
    if not a.plaintext:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(a.cert)
    print(f"mock upload server on {a.host}:{a.port} ({'plaintext' if a.plaintext else 'TLS'}) — SANDBOX ONLY", flush=True)
    try:
        while True:
            conn, addr = srv.accept()
            if ctx:
                try:
                    conn = ctx.wrap_socket(conn, server_side=True)
                except ssl.SSLError as e:
                    print(f"[{addr[1]}] TLS handshake failed: {e}", flush=True); continue
            threading.Thread(target=handle, args=(conn, addr, a), daemon=True).start()
    except KeyboardInterrupt:
        print("\nshutting down")
    finally:
        srv.close()


if __name__ == "__main__":
    main()
