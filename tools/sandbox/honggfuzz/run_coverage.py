#!/usr/bin/env python3
"""Wrapper for the coverage-guided honggfuzz netdriver scaffold.

This path uses the small C target in `upload_netdriver.c`. The script manages the
seed corpus and artifact directories, then prints or runs the honggfuzz command
that keeps the netdriver target pinned to localhost.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SEEDER = SCRIPT_DIR / "seed_upload_corpus.py"
TARGET_SRC = SCRIPT_DIR / "upload_netdriver.c"
TARGET_BIN = SCRIPT_DIR / "upload_netdriver"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def compile_target(compiler: str, extra_cflags: list[str], out: Path, source: Path) -> None:
    cmd = [compiler, "-O1", "-g", "-Wall", "-Wextra", "-o", str(out), str(source)] + extra_cflags
    subprocess.run(cmd, check=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--honggfuzz", default="honggfuzz", help="honggfuzz executable")
    ap.add_argument(
        "--compiler",
        default=os.environ.get("CC") or shutil.which("hfuzz-clang") or shutil.which("hfuzz-gcc") or "cc",
    )
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8443)
    ap.add_argument("--corpus", default=str(SCRIPT_DIR / "runtime" / "coverage" / "corpus"))
    ap.add_argument("--output", default=str(SCRIPT_DIR / "runtime" / "coverage" / "output"))
    ap.add_argument("--workspace", default=str(SCRIPT_DIR / "runtime" / "coverage" / "workspace"))
    ap.add_argument("--crashdir", default=str(SCRIPT_DIR / "runtime" / "coverage" / "crashes"))
    ap.add_argument("--binary", default=str(TARGET_BIN))
    ap.add_argument("--dry-run", action="store_true", help="print the exact commands and exit")
    ap.add_argument("--no-build", action="store_true", help="skip compiling the C scaffold")
    args = ap.parse_args()

    if not SEEDER.is_file() or not TARGET_SRC.is_file():
        raise SystemExit("honggfuzz helpers are missing")

    corpus = ensure_dir(Path(args.corpus).expanduser())
    output = ensure_dir(Path(args.output).expanduser())
    workspace = ensure_dir(Path(args.workspace).expanduser())
    crashdir = ensure_dir(Path(args.crashdir).expanduser())
    binary = Path(args.binary).expanduser()

    seed_cmd = [sys.executable, str(SEEDER), "--corpus-dir", str(corpus)]
    build_cmd = [args.compiler, "-O1", "-g", "-Wall", "-Wextra", "-o", str(binary), str(TARGET_SRC)]
    fuzz_cmd = [
        args.honggfuzz,
        "--netdriver",
        "--persistent",
        "-i", str(corpus),
        "--output", str(output),
        "--workspace", str(workspace),
        "--crashdir", str(crashdir),
        "--",
        str(binary),
        "--port", str(args.port),
    ]
    env = os.environ.copy()
    env["HFND_TCP_PORT"] = str(args.port)
    fuzz_display = "HFND_TCP_PORT={} ".format(args.port) + " ".join(fuzz_cmd)

    print("seeding corpus:", " ".join(seed_cmd))
    if not args.no_build:
        print("building target:", " ".join(build_cmd))
    if args.dry_run:
        print("running honggfuzz:", fuzz_display)
        return 0

    subprocess.run(seed_cmd, check=True)
    if not args.no_build:
        subprocess.run(build_cmd, check=True)
    print("running honggfuzz:", fuzz_display)
    return subprocess.call(fuzz_cmd, env=env)


if __name__ == "__main__":
    import os

    raise SystemExit(main())
