#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import struct
import sys


def le_u32(value: int) -> bytes:
    return struct.pack("<I", value)


def make_case(call_mode: int, pixfmt: int, width: int, height: int, payload: bytes) -> bytes:
    header = bytearray()
    header += b"FIMU"
    header += bytes([1, call_mode, pixfmt, 0])
    header += le_u32(width)
    header += le_u32(height)
    header += le_u32(len(payload))
    return bytes(header) + payload


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: make_seeds.py <seed-dir>", file=sys.stderr)
        return 2

    out_dir = pathlib.Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)

    seeds = {
        "seed-raw-buffer.fimu": make_case(
            0,
            2,
            8,
            8,
            bytes(range(64)),
        ),
        "seed-flat-gray.fimu": make_case(
            1,
            0,
            8,
            8,
            bytes([0x80]) * 96,
        ),
        "seed-gradient.fimu": make_case(
            1,
            1,
            16,
            16,
            bytes((i * 3) & 0xFF for i in range(384)),
        ),
    }

    for name, data in seeds.items():
        (out_dir / name).write_bytes(data)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
