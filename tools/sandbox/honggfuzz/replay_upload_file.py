#!/usr/bin/env python3
"""Black-box honggfuzz replay driver for the upload protocol surface.

Honggfuzz mutates an input file in `-x` mode; this wrapper:
  1. opens a local connection to the sandbox upload mock,
  2. sends a deterministic HELLO handshake, then
  3. replays the file bytes verbatim as post-HELLO protocol traffic.

That lets honggfuzz explore the opcode/length surface without needing a C harness.
"""
from __future__ import annotations

import argparse
import json
import socket
import ssl
import struct
from pathlib import Path


OK, HELLO, PROTO = 1, 2, 3


def be_long(value: int) -> bytes:
    return struct.pack(">q", value)


def connect(host: str, port: int, plaintext: bool, timeout: float) -> socket.socket:
    sock = socket.create_connection((host, port), timeout=timeout)
    if not plaintext:
        ctx = ssl._create_unverified_context()
        sock = ctx.wrap_socket(sock, server_hostname=host)
    sock.settimeout(timeout)
    return sock


def recvn(sock: socket.socket, size: int) -> bytes:
    buf = b""
    while len(buf) < size:
        chunk = sock.recv(size - len(buf))
        if not chunk:
            raise ConnectionError("peer closed")
        buf += chunk
    return buf


def send_hello(sock: socket.socket, token: str) -> None:
    payload = json.dumps({
        "authToken": token,
        "serial": "MOCK-000000",
        "clientVersion": "honggfuzz-blackbox",
    }, separators=(",", ":")).encode("utf-8")
    sock.sendall(bytes([HELLO, PROTO]))
    sock.sendall(be_long(len(payload)))
    sock.sendall(payload)
    n = struct.unpack(">q", recvn(sock, 8))[0]
    recvn(sock, n)
    sock.sendall(bytes([OK]))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input_file", help="honggfuzz-provided file path (___FILE___)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8443)
    ap.add_argument("--plaintext", action="store_true", help="disable TLS for the local mock")
    ap.add_argument("--timeout", type=float, default=5.0)
    ap.add_argument("--token", default="SANDBOX-FAKE-TOKEN")
    args = ap.parse_args()

    input_path = Path(args.input_file)
    if not input_path.is_file():
        raise SystemExit(f"input file not found: {input_path}")

    payload = input_path.read_bytes()
    sock = connect(args.host, args.port, args.plaintext, args.timeout)
    try:
        send_hello(sock, args.token)
        if payload:
            sock.sendall(payload)
        try:
            sock.shutdown(socket.SHUT_WR)
        except OSError:
            pass
        while sock.recv(4096):
            pass
    finally:
        sock.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
