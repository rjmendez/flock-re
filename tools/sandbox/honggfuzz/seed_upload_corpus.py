#!/usr/bin/env python3
"""Seed corpus generator for the honggfuzz upload-protocol workflows.

The seeds are synthetic and safe: they start *after* a valid HELLO exchange so the
black-box driver can prepend its own deterministic handshake and then replay these
bytes as raw protocol traffic.
"""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path


OK, HELLO, PROTO, SESSION, START, FILE, HASH, SAVE, COMPLETE, METADATA = (
    1, 2, 3, 4, 5, 6, 7, 8, 9, 12,
)


def be_long(value: int) -> bytes:
    return struct.pack(">q", value)


def build_seeds() -> dict[str, bytes]:
    minimal_meta = json.dumps({
        "cameraSerial": "MOCK-000000",
        "createdAt": 1,
        "detections": [],
    }, separators=(",", ":")).encode("utf-8")
    minimal_file = b"F"

    return {
        "00-session-start.bin": bytes([SESSION, START]),
        "01-metadata-file-hash.bin": (
            bytes([METADATA]) + be_long(len(minimal_meta)) + minimal_meta +
            bytes([FILE]) + be_long(len(minimal_file)) + minimal_file +
            bytes([HASH]) + b"\x00" * 32 +
            bytes([SAVE, COMPLETE, SESSION])
        ),
        "02-short-file-smuggle.bin": bytes([FILE]) + be_long(1) + b"A" + bytes([200]),
        "03-length-edge-cases.bin": (
            bytes([METADATA]) + be_long(0) +
            bytes([FILE]) + be_long(-1) +
            bytes([HASH]) + b"\x00" * 31
        ),
    }


def write_seeds(corpus_dir: Path, overwrite: bool) -> list[Path]:
    corpus_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, data in build_seeds().items():
        path = corpus_dir / name
        if path.exists() and not overwrite:
            continue
        path.write_bytes(data)
        written.append(path)
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus-dir", required=True, help="directory to seed")
    ap.add_argument("--overwrite", action="store_true", help="replace existing seeds")
    ap.add_argument("--json", action="store_true", help="emit a JSON manifest on stdout")
    args = ap.parse_args()

    corpus_dir = Path(args.corpus_dir).expanduser()
    if corpus_dir.exists() and not corpus_dir.is_dir():
        raise SystemExit(f"--corpus-dir is not a directory: {corpus_dir}")

    written = write_seeds(corpus_dir, args.overwrite)
    skipped = sorted(p.name for p in corpus_dir.iterdir() if p.is_file()) if corpus_dir.exists() else []

    if args.json:
        print(json.dumps({
            "corpus_dir": str(corpus_dir),
            "written": [str(p) for p in written],
            "seed_names": sorted(build_seeds().keys()),
        }, indent=2))
    else:
        print(f"seeded {len(written)} file(s) in {corpus_dir}")
        if written:
            for path in written:
                print(f"  wrote {path.name}")
        else:
            print("  no files rewritten (already seeded)")
        if skipped:
            print(f"  existing files: {', '.join(skipped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
