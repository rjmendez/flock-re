#!/usr/bin/env python3
"""Bounded reaperd socket preflight/probe lane.

Classifies runtime availability blockers explicitly before any reaperd fuzz claims.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass


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


def _adb_shell(serial: str, shell_cmd: str, timeout_sec: int) -> tuple[int, str, str]:
    return _run(["adb", "-s", serial, "shell", "sh", "-c", shell_cmd], timeout_sec=timeout_sec)


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def _check_socket_exists(serial: str, path: str, timeout_sec: int) -> CheckResult:
    code, out, err = _adb_shell(serial, f"test -S {path} >/dev/null 2>&1; echo $?", timeout_sec)
    ok = code == 0 and out.strip().endswith("0")
    return CheckResult("reaperd-socket-exists", ok, out.strip() or err)


def _check_nc_available(serial: str, timeout_sec: int) -> CheckResult:
    code, out, err = _adb_shell(serial, "command -v toybox >/dev/null 2>&1; echo $?", timeout_sec)
    ok = code == 0 and out.strip().endswith("0")
    return CheckResult("toybox-available", ok, out.strip() or err)


def _probe_socket(serial: str, path: str, timeout_sec: int) -> CheckResult:
    probe = f"printf 'PING' | toybox nc -U -w 1 {path} >/dev/null 2>&1; echo $?"
    code, out, err = _adb_shell(serial, probe, timeout_sec)
    ok = code == 0 and out.strip().endswith("0")
    return CheckResult("reaperd-socket-connect", ok, out.strip() or err)


def _check_reaperd_process(serial: str, timeout_sec: int) -> CheckResult:
    code, out, err = _adb_shell(serial, "ps -A | grep -i reaperd >/dev/null 2>&1; echo $?", timeout_sec)
    ok = code == 0 and out.strip().endswith("0")
    return CheckResult("reaperd-process-present", ok, out.strip() or err)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", default="", help="ADB serial; defaults to first emulator-* device.")
    parser.add_argument("--socket-path", default="/dev/socket/reaperd")
    parser.add_argument("--timeout-sec", type=int, default=5)
    parser.add_argument("--execute-connect", action="store_true", help="Attempt bounded socket connect probe.")
    parser.add_argument(
        "--virtualized-allow-missing-socket",
        action="store_true",
        help="Treat missing socket as non-blocking for virtualized analysis lanes.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    serial = args.serial or _discover_serial()
    if not serial:
        payload = {"ok": False, "blocked": True, "error": "No adb device in state 'device' found."}
        print(json.dumps(payload, indent=2) if args.json else payload["error"])
        return 2

    checks = [_check_socket_exists(serial, args.socket_path, max(1, args.timeout_sec))]
    checks.append(_check_nc_available(serial, max(1, args.timeout_sec)))

    if args.execute_connect and checks[0].ok and checks[1].ok:
        checks.append(_probe_socket(serial, args.socket_path, max(1, args.timeout_sec)))

    blockers = []
    if not checks[0].ok:
        blockers.append(f"Missing runtime socket: {args.socket_path}")
    if args.execute_connect and not checks[1].ok:
        blockers.append("toybox is unavailable; cannot run bounded UNIX-socket connect probe.")
    if args.execute_connect and len(checks) == 3 and not checks[2].ok:
        blockers.append("Socket connect probe failed (EOF/refusal/timeout).")

    virtualized_override = False
    virtualized_note = ""
    if args.virtualized_allow_missing_socket and blockers:
        process_check = _check_reaperd_process(serial, max(1, args.timeout_sec))
        checks.append(process_check)
        if not checks[0].ok and not process_check.ok:
            virtualized_override = True
            virtualized_note = "reaperd socket/process absent on target; classified as virtualized-only lane."
            blockers = []

    payload = {
        "ok": len(blockers) == 0,
        "blocked": len(blockers) > 0,
        "serial": serial,
        "socket_path": args.socket_path,
        "execute_connect": args.execute_connect,
        "virtualized_override": virtualized_override,
        "virtualized_note": virtualized_note,
        "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail} for c in checks],
        "blockers": blockers,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"serial={serial} socket={args.socket_path} ok={payload['ok']}")
        for item in payload["checks"]:
            print(f"check {item['name']}: {item['ok']} ({item['detail']})")
    return 0 if payload["ok"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
