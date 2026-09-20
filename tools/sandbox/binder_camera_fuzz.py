#!/usr/bin/env python3
"""Bounded Binder camera probe/fuzz lane for sandbox testing.

This tool is local-only and defaults to dry-run. It targets Binder camera services
(`media.camera` / `media.camera.proxy`) via adb shell commands with strict limits.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time

ALLOWED_SERVICES = {"media.camera", "media.camera.proxy"}


def _run(cmd: list[str], timeout_sec: int) -> tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        check=False,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _discover_serial() -> str:
    code, out, _ = _run(["adb", "devices"], timeout_sec=5)
    if code != 0:
        return ""
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device" and parts[0].startswith("emulator-"):
            return parts[0]
    return ""


def _build_steps(service: str, max_ops: int) -> list[list[str]]:
    # Deterministic and bounded; these are safe introspection-ish probes.
    base_steps = [
        ["service", "list"],
        ["service", "check", service],
        ["service", "call", service, "1"],
        ["service", "call", service, "2"],
    ]
    return base_steps[: max(1, min(max_ops, len(base_steps)))]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--serial", default="", help="ADB device serial. Defaults to first emulator-* device.")
    ap.add_argument(
        "--service",
        default="media.camera",
        choices=sorted(ALLOWED_SERVICES),
        help="Binder camera service target.",
    )
    ap.add_argument("--max-ops", type=int, default=4, help="Maximum bounded probe ops (1-8).")
    ap.add_argument("--timeout-sec", type=int, default=5, help="Per-command timeout in seconds.")
    ap.add_argument("--execute", action="store_true", help="Execute probes (default is dry-run).")
    ap.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = ap.parse_args()

    max_ops = max(1, min(args.max_ops, 8))
    serial = args.serial or _discover_serial()
    if not serial:
        msg = {"ok": False, "error": "No adb device in state 'device' found.", "dry_run": not args.execute}
        print(json.dumps(msg, indent=2) if args.json else msg["error"])
        return 2

    steps = _build_steps(args.service, max_ops)
    commands = [["adb", "-s", serial, "shell"] + step for step in steps]
    results: list[dict[str, object]] = []

    if args.execute:
        for cmd in commands:
            t0 = time.time()
            code, out, err = _run(cmd, timeout_sec=max(1, args.timeout_sec))
            results.append(
                {
                    "cmd": cmd,
                    "returncode": code,
                    "stdout": out,
                    "stderr": err,
                    "elapsed_ms": int((time.time() - t0) * 1000),
                }
            )

    payload = {
        "ok": True,
        "serial": serial,
        "service": args.service,
        "dry_run": not args.execute,
        "max_ops": max_ops,
        "commands": commands,
        "results": results,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"serial={serial} service={args.service} dry_run={not args.execute} max_ops={max_ops}")
        for cmd in commands:
            print("route command:", " ".join(cmd))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

