#!/usr/bin/env python3
"""Wrapper for black-box honggfuzz runs against the Python upload mock.

Workflow:
  - seed a corpus directory with safe protocol transcripts,
  - start the existing Python `upload_server.py` mock in plaintext mode,
  - run honggfuzz in `-x` file mode against `replay_upload_file.py`, and
  - write artifacts to deterministic corpus/output/workspace/crash locations.

This is intentionally separate from the coverage-guided C netdriver scaffold.
"""
from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
UPLOAD_SERVER = ROOT / "upload_server.py"
SEEDER = SCRIPT_DIR / "seed_upload_corpus.py"
REPLAYER = SCRIPT_DIR / "replay_upload_file.py"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def wait_for_port(host: str, port: int, timeout_s: float) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return
        except OSError:
            time.sleep(0.2)
    raise SystemExit(f"server did not become ready on {host}:{port} within {timeout_s}s")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--honggfuzz", default="honggfuzz", help="honggfuzz executable")
    ap.add_argument("--python", default=sys.executable, help="Python interpreter to use")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8443)
    ap.add_argument("--corpus", default=str(SCRIPT_DIR / "runtime" / "blackbox" / "corpus"))
    ap.add_argument("--output", default=str(SCRIPT_DIR / "runtime" / "blackbox" / "output"))
    ap.add_argument("--workspace", default=str(SCRIPT_DIR / "runtime" / "blackbox" / "workspace"))
    ap.add_argument("--crashdir", default=str(SCRIPT_DIR / "runtime" / "blackbox" / "crashes"))
    ap.add_argument("--server-timeout", type=float, default=8.0)
    ap.add_argument("--dry-run", action="store_true", help="print the exact command and exit")
    args = ap.parse_args()

    if not UPLOAD_SERVER.is_file():
        raise SystemExit(f"missing target server: {UPLOAD_SERVER}")
    if not SEEDER.is_file() or not REPLAYER.is_file():
        raise SystemExit("honggfuzz helper scripts are missing")

    corpus = ensure_dir(Path(args.corpus).expanduser())
    output = ensure_dir(Path(args.output).expanduser())
    workspace = ensure_dir(Path(args.workspace).expanduser())
    crashdir = ensure_dir(Path(args.crashdir).expanduser())

    seed_cmd = [args.python, str(SEEDER), "--corpus-dir", str(corpus)]
    server_cmd = [
        args.python, str(UPLOAD_SERVER),
        "--host", args.host,
        "--port", str(args.port),
        "--plaintext",
    ]
    fuzz_cmd = [
        args.honggfuzz,
        "-x",
        "-i", str(corpus),
        "--output", str(output),
        "--workspace", str(workspace),
        "--crashdir", str(crashdir),
        "--",
        args.python, str(REPLAYER),
        "--host", args.host,
        "--port", str(args.port),
        "--plaintext",
        "___FILE___",
    ]

    print("seeding corpus:", " ".join(seed_cmd))
    if args.dry_run:
        print("starting server:", " ".join(server_cmd))
        print("running honggfuzz:", " ".join(fuzz_cmd))
        return 0

    subprocess.run(seed_cmd, check=True)
    server = subprocess.Popen(server_cmd)
    try:
        wait_for_port(args.host, args.port, args.server_timeout)
        print("running honggfuzz:", " ".join(fuzz_cmd))
        return subprocess.call(fuzz_cmd)
    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
