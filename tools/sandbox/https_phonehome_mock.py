#!/usr/bin/env python3
import argparse
import json
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class PhonehomeHandler(BaseHTTPRequestHandler):
    server_version = 'PhonehomeMock/1.0'

    def _write_json(self, status_code: int, payload: dict):
        body = json.dumps(payload, separators=(',', ':')).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        _ = self.rfile.read(int(self.headers.get('Content-Length', '0') or '0'))
        payload = {
            'status': True,
            'fail_reason': '',
            'mock': True,
            'path': self.path,
        }
        self._write_json(200, payload)

    def do_GET(self):
        payload = {
            'status': True,
            'fail_reason': '',
            'mock': True,
            'path': self.path,
        }
        self._write_json(200, payload)

    def log_message(self, fmt, *args):
        print(f'[http-mock] {self.address_string()} {fmt % args}')


def build_server(host: str, port: int, cert: str, plaintext: bool) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), PhonehomeHandler)
    if plaintext:
        return server

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    return server


def main():
    ap = argparse.ArgumentParser(description='HTTPS phonehome mock endpoint for emulator fake-C2 testing.')
    ap.add_argument('--host', default='0.0.0.0')
    ap.add_argument('--port', type=int, default=18443)
    ap.add_argument('--cert', default='tools/sandbox/server.pem')
    ap.add_argument('--plaintext', action='store_true', help='Run plain HTTP for local tests.')
    args = ap.parse_args()

    server = build_server(args.host, args.port, args.cert, args.plaintext)
    mode = 'HTTP' if args.plaintext else 'HTTPS'
    print(f'phonehome mock listening on {args.host}:{args.port} ({mode})', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
