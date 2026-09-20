#!/usr/bin/env python3
"""Deterministic wrappers for non-upload sandbox probe routes.

Adds lightweight, executable entrypoints for undercovered surfaces:
  - GPS/log evidence scanning over unpacked crash artifacts
  - protocol/control-plane ack-state probing
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SANDBOX_DIR = SCRIPT_DIR.parent
GPS_LOG_PROBE = SANDBOX_DIR / "crashpack_coordinate_probe.py"
CONTROL_PROBE = SANDBOX_DIR / "hello_ack_probe.py"


def run_cmd(cmd: list[str], dry_run: bool) -> int:
    print("route command:", " ".join(cmd))
    if dry_run:
        return 0
    return subprocess.call(cmd)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable, help="Python interpreter to use")
    sub = parser.add_subparsers(dest="route", required=True)

    gps = sub.add_parser("gps-log", help="scan crash-pack artifacts for GPS/log coordinate evidence")
    gps.add_argument(
        "--path",
        default=str(SANDBOX_DIR / "campaign_results"),
        help="Crash-pack root or log file path (default: sandbox campaign_results)",
    )
    gps.add_argument("--max-samples", type=int, default=3, help="Sample lines per file")
    gps.add_argument("--json", action="store_true", help="Output JSON summary")
    gps.add_argument("--dry-run", action="store_true", help="Print command only")

    control = sub.add_parser("protocol-control", help="probe HELLO ack/control-plane handling")
    control.add_argument("--host", default="127.0.0.1")
    control.add_argument("--port", type=int, default=8443)
    control.add_argument("--ack", type=int, default=12, help="Bogus ack byte to send")
    control.add_argument("--token", default="SANDBOX-FAKE-TOKEN")
    control.add_argument("--plaintext", action="store_true", help="Use plaintext mode")
    control.add_argument("--dry-run", action="store_true", help="Print command only")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.route == "gps-log":
        if not GPS_LOG_PROBE.is_file():
            raise SystemExit(f"missing GPS/log probe: {GPS_LOG_PROBE}")
        cmd = [
            args.python,
            str(GPS_LOG_PROBE),
            str(Path(args.path).expanduser()),
            "--max-samples",
            str(args.max_samples),
        ]
        if args.json:
            cmd.append("--json")
        return run_cmd(cmd, args.dry_run)

    if not CONTROL_PROBE.is_file():
        raise SystemExit(f"missing protocol-control probe: {CONTROL_PROBE}")
    cmd = [
        args.python,
        str(CONTROL_PROBE),
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--ack",
        str(args.ack),
        "--token",
        args.token,
    ]
    if args.plaintext:
        cmd.append("--plaintext")
    return run_cmd(cmd, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
