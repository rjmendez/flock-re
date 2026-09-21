#!/usr/bin/env python3
"""Deterministic wrappers for non-upload sandbox probe routes.

Adds lightweight, executable entrypoints for undercovered surfaces:
  - GPS/log evidence scanning over unpacked crash artifacts
  - protocol/control-plane ack-state probing
  - endpoint-map quality gating
  - runtime preflight for camera/reaperd lanes
  - telemetry simulation dataset capture
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
ENDPOINT_GATE = SANDBOX_DIR / "endpoint_map_quality_gate.py"
CAMERA_PROBE = SANDBOX_DIR / "binder_camera_fuzz.py"
REAPERD_PROBE = SANDBOX_DIR / "reaperd_wire_probe.py"
TELEMETRY_CAPTURE = SANDBOX_DIR / "telemetry_sim_capture.py"


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

    endpoint = sub.add_parser("endpoint-map-gate", help="run endpoint-map normalization quality gate")
    endpoint.add_argument(
        "--analysis-json",
        default="artifact-staging/fleetlog_real_corpus/full_crashpack_analysis.json",
    )
    endpoint.add_argument("--min-valid-domain-ratio", type=float, default=0.8)
    endpoint.add_argument("--max-uncertain-token-ratio", type=float, default=0.2)
    endpoint.add_argument("--min-high-confidence-hosts", type=int, default=3)
    endpoint.add_argument("--dry-run", action="store_true", help="Print command only")

    camera = sub.add_parser("camera-preflight", help="run bounded camera runtime preflight")
    camera.add_argument("--serial", default="")
    camera.add_argument("--service", default="media.camera")
    camera.add_argument("--required-socket", default="/data/vendor/camera/cam_socket0")
    camera.add_argument("--dry-run", action="store_true", help="Print command only")

    reaperd = sub.add_parser("reaperd-preflight", help="run bounded reaperd runtime preflight")
    reaperd.add_argument("--serial", default="")
    reaperd.add_argument("--socket-path", default="/dev/socket/reaperd")
    reaperd.add_argument("--execute-connect", action="store_true")
    reaperd.add_argument("--dry-run", action="store_true", help="Print command only")

    telemetry = sub.add_parser("telemetry-capture", help="collect/parse telemetry simulation dataset")
    telemetry.add_argument("--mode", choices=["collect", "parse"], default="parse")
    telemetry.add_argument("--min-rows", type=int, default=6)
    telemetry.add_argument("--dry-run", action="store_true", help="Print command only")
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

    if args.route == "protocol-control":
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

    if args.route == "endpoint-map-gate":
        if not ENDPOINT_GATE.is_file():
            raise SystemExit(f"missing endpoint gate: {ENDPOINT_GATE}")
        cmd = [
            args.python,
            str(ENDPOINT_GATE),
            "--analysis-json",
            args.analysis_json,
            "--min-valid-domain-ratio",
            str(args.min_valid_domain_ratio),
            "--max-uncertain-token-ratio",
            str(args.max_uncertain_token_ratio),
            "--min-high-confidence-hosts",
            str(args.min_high_confidence_hosts),
        ]
        return run_cmd(cmd, args.dry_run)

    if args.route == "camera-preflight":
        if not CAMERA_PROBE.is_file():
            raise SystemExit(f"missing camera probe: {CAMERA_PROBE}")
        cmd = [
            args.python,
            str(CAMERA_PROBE),
            "--json",
            "--service",
            args.service,
            "--required-socket",
            args.required_socket,
        ]
        if args.serial:
            cmd.extend(["--serial", args.serial])
        return run_cmd(cmd, args.dry_run)

    if args.route == "reaperd-preflight":
        if not REAPERD_PROBE.is_file():
            raise SystemExit(f"missing reaperd probe: {REAPERD_PROBE}")
        cmd = [
            args.python,
            str(REAPERD_PROBE),
            "--json",
            "--socket-path",
            args.socket_path,
        ]
        if args.serial:
            cmd.extend(["--serial", args.serial])
        if args.execute_connect:
            cmd.append("--execute-connect")
        return run_cmd(cmd, args.dry_run)

    if not TELEMETRY_CAPTURE.is_file():
        raise SystemExit(f"missing telemetry capture: {TELEMETRY_CAPTURE}")
    cmd = [
        args.python,
        str(TELEMETRY_CAPTURE),
        "--mode",
        args.mode,
        "--min-rows",
        str(args.min_rows),
    ]
    return run_cmd(cmd, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
