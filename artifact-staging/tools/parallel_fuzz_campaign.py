#!/usr/bin/env python3

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def repo_root() -> Path:
    start = Path(__file__).resolve()
    for candidate in (start.parents[2], start.parents[1], start.parent):
        if (candidate / "artifact-staging").exists():
            return candidate
    return Path.cwd()


def run_cmd(args: list[str], timeout: int | None = None) -> dict:
    cp = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    return {
        "args": args,
        "returncode": cp.returncode,
        "stdout": cp.stdout or "",
        "stderr": cp.stderr or "",
    }


def run_endpoint_campaign(
    python_exe: str,
    root: Path,
    serial: str,
    results_dir: Path,
    endpoint_runs: int,
    guidance_file: str,
) -> dict:
    tool = root / "artifact-staging" / "tools" / "targeted_provider_endpoint_r2.py"
    campaign_dir = results_dir / f"endpoint_parallel_{now_stamp()}_{serial.replace(':', '_')}"
    campaign_dir.mkdir(parents=True, exist_ok=True)

    runs = []
    for i in range(1, endpoint_runs + 1):
        out_dir = campaign_dir / f"run_{i:03d}"
        cmd = [
            python_exe,
            str(tool),
            "--root",
            str(root / "artifact-staging"),
            "--serial",
            serial,
            "--out-dir",
            str(out_dir),
        ]
        if guidance_file:
            cmd.extend(["--guidance-file", guidance_file])

        rec = run_cmd(cmd)
        rec["run"] = i
        rec["out_dir"] = str(out_dir)
        report_path = out_dir / "targeted_report.json"
        if report_path.exists():
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
                s1 = report["todo_results"]["fuzz-targeted-001-provider-npe-space"]["summary"]
                s4 = report["todo_results"]["fuzz-targeted-004-endpoint-egress-guard-abuse"]["summary"]
                rec["summary"] = {
                    "cases": s1.get("total_cases"),
                    "npe_cases": len(s1.get("provider_npe_cases", [])),
                    "fatal": bool(s1.get("fatal_exception_in_logcat")),
                    "attempts": s4.get("attempt_count"),
                    "reach": bool(s4.get("real_endpoint_reached_any")),
                }
            except Exception as exc:
                rec["summary_error"] = str(exc)
        runs.append(rec)

    return {"campaign_dir": str(campaign_dir), "runs": runs}


def run_live_fuzz(
    python_exe: str,
    root: Path,
    serial: str,
    results_dir: Path,
    adb_path: str,
    package_filter: str,
    timeout_seconds: int,
    events: int,
    max_packages: int,
) -> dict:
    tool = root / "artifact-staging" / "tools" / "live_fuzz_runner.py"
    cmd = [
        python_exe,
        str(tool),
        "--adb-path",
        adb_path,
        "--serial",
        serial,
        "--package-filter",
        package_filter,
        "--timeout-seconds",
        str(timeout_seconds),
        "--events",
        str(events),
        "--max-packages",
        str(max_packages),
        "--results-dir",
        str(results_dir),
    ]
    return run_cmd(cmd, timeout=max(120, timeout_seconds * max(1, max_packages or 3) + 120))


def serial_worker(args, serial: str) -> dict:
    root = Path(args.root).resolve()
    results_dir = Path(args.results_dir).resolve()
    results_dir.mkdir(parents=True, exist_ok=True)

    mode = args.serial_mode_map.get(serial, args.mode)
    worker_result = {"serial": serial, "mode": mode, "endpoint": None, "live": None}
    if mode in ("endpoint", "both"):
        worker_result["endpoint"] = run_endpoint_campaign(
            python_exe=sys.executable,
            root=root,
            serial=serial,
            results_dir=results_dir,
            endpoint_runs=args.endpoint_runs,
            guidance_file=args.guidance_file,
        )
    if mode in ("live", "both"):
        worker_result["live"] = run_live_fuzz(
            python_exe=sys.executable,
            root=root,
            serial=serial,
            results_dir=results_dir,
            adb_path=args.adb_path,
            package_filter=args.package_filter,
            timeout_seconds=args.timeout_seconds,
            events=args.events,
            max_packages=args.max_packages,
        )
    return worker_result


def parse_args():
    root = repo_root()
    default_adb = root / "artifact-staging" / "tools" / "platform-tools" / "adb.exe"
    ap = argparse.ArgumentParser(
        description="Run fuzzing in parallel across multiple device serials (one worker per serial)."
    )
    ap.add_argument("--serials", required=True, help="Comma-separated adb serials, e.g. emulator-5554,emulator-5556")
    ap.add_argument("--mode", choices=["endpoint", "live", "both"], default="both")
    ap.add_argument(
        "--serial-modes",
        default="",
        help="Optional per-serial mode overrides, e.g. emulator-5554:endpoint,emulator-5556:live",
    )
    ap.add_argument("--endpoint-runs", type=int, default=5)
    ap.add_argument("--guidance-file", default="")
    ap.add_argument("--adb-path", default=str(default_adb))
    ap.add_argument("--package-filter", default="flock")
    ap.add_argument("--timeout-seconds", type=int, default=180)
    ap.add_argument("--events", type=int, default=1200)
    ap.add_argument("--max-packages", type=int, default=0)
    ap.add_argument("--root", default=str(root))
    ap.add_argument("--results-dir", default=str(root / "artifact-staging" / "results"))
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    serials = [s.strip() for s in args.serials.split(",") if s.strip()]
    if not serials:
        print("[ERROR] No valid serials parsed from --serials", file=sys.stderr)
        return 1
    serial_mode_map = {}
    if args.serial_modes:
        for pair in args.serial_modes.split(","):
            pair = pair.strip()
            if not pair or ":" not in pair:
                continue
            serial, mode = pair.split(":", 1)
            serial = serial.strip()
            mode = mode.strip()
            if serial and mode in {"endpoint", "live", "both"}:
                serial_mode_map[serial] = mode
    args.serial_mode_map = serial_mode_map

    started = datetime.now(timezone.utc).isoformat()
    results = []
    with ThreadPoolExecutor(max_workers=len(serials)) as ex:
        futures = {ex.submit(serial_worker, args, serial): serial for serial in serials}
        for fut in as_completed(futures):
            serial = futures[fut]
            try:
                results.append(fut.result())
                print(f"[OK] serial={serial} worker complete")
            except Exception as exc:
                results.append({"serial": serial, "error": str(exc)})
                print(f"[ERROR] serial={serial} worker failed: {exc}", file=sys.stderr)

    summary = {
        "started_at_utc": started,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "serial_count": len(serials),
        "serials": serials,
        "mode": args.mode,
        "serial_mode_overrides": serial_mode_map,
        "results": results,
    }
    out = Path(args.results_dir) / f"parallel_fuzz_summary_{now_stamp()}.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Summary: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
