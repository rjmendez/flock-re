#!/usr/bin/env python3

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def repo_root() -> Path:
    start = Path(__file__).resolve()
    for candidate in (start.parents[2], start.parents[1], start.parent):
        if (candidate / "artifact-staging").exists():
            return candidate
    return Path.cwd()


def default_adb_path() -> Path:
    root = repo_root()
    candidate = root / "artifact-staging" / "tools" / "platform-tools" / "adb.exe"
    if candidate.exists():
        return candidate
    return Path("adb")


def sanitize_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "package"


def run_command(args, timeout: int | None = None):
    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        out, err = proc.communicate(timeout=timeout)
        return {"returncode": proc.returncode, "stdout": out or "", "stderr": err or "", "timed_out": False}
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
        return {"returncode": -999, "stdout": out or "", "stderr": err or "", "timed_out": True}


PACKAGE_PATTERN = re.compile(r"(?:[a-zA-Z_][a-zA-Z0-9_]*\.)+[a-zA-Z_][a-zA-Z0-9_]*")
DEFAULT_FLOCK_PREFIXES = ("com.flock.", "ai.flock.", "flock.")
DEFAULT_FLOCK_ALLOWLIST = {
    "com.flock",
    "ai.flock",
}


def extract_crash_lines(logcat_text: str, package: str):
    if not logcat_text:
        return []
    patterns = (
        r"fatal exception",
        r"androidruntime",
        r"classnotfoundexception",
        r"resources\$notfoundexception",
        r"failed to open dex",
        r"unable to open dex",
        r"anr in",
        r"force-killing crashed app",
        r"native crash",
        r"sigsegv|sigabrt",
    )
    lines = []
    for line in logcat_text.splitlines():
        low = line.lower()
        if not any(re.search(pattern, low) for pattern in patterns):
            continue

        mentions = PACKAGE_PATTERN.findall(line)
        if mentions and package not in mentions:
            continue
        lines.append(line)
    return lines


def write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def normalize_scope_lists(prefixes: list[str], allowlist: list[str]):
    normalized_prefixes = []
    for prefix in prefixes:
        value = (prefix or "").strip()
        if not value:
            continue
        normalized_prefixes.append(value if value.endswith(".") else f"{value}.")
    normalized_allowlist = {item.strip() for item in allowlist if (item or "").strip()}
    return sorted(set(normalized_prefixes)), sorted(normalized_allowlist)


def is_flock_scoped_package(package: str, allowed_prefixes: list[str], allowed_exact: list[str]):
    if package in allowed_exact:
        return True, "allowlisted"
    for prefix in allowed_prefixes:
        if package.startswith(prefix):
            return True, "prefix_allowed"
    return False, "skipped_non_flock"


def list_packages(adb_path: Path, serial: str, package_filter: str):
    cmd = [str(adb_path), "-s", serial, "shell", "pm", "list", "packages"]
    result = run_command(cmd, timeout=30)
    if result["returncode"] != 0:
        raise RuntimeError(f"adb pm list packages failed: {result['stderr'] or result['stdout'] or 'unknown error'}")

    package_names = []
    for line in result["stdout"].splitlines():
        line = line.strip()
        if not line.startswith("package:"):
            continue
        pkg = line.split(":", 1)[1].strip()
        if not pkg:
            continue
        if package_filter.lower() in pkg.lower():
            package_names.append(pkg)
    return sorted(set(package_names))


def build_markdown(summary: dict) -> str:
    lines = [
        "# Live APK/Device Fuzz Summary",
        "",
        f"- Device: {summary.get('device', 'unknown')}",
        f"- Filter: {summary.get('package_filter', 'n/a')}",
        f"- Dry run: {str(summary.get('dry_run', False)).lower()}",
        f"- Packages processed: {summary.get('package_count', 0)}",
        "",
        "| Package | Status | Cause | Exit | Timed Out | Crash Lines |",
        "|---|---|---|---:|---:|---:|",
    ]
    for row in summary.get("results", []):
        lines.append(
            f"| {row.get('package', 'unknown')} | {row.get('status', 'unknown')} | {row.get('cause_category', 'unknown')} | {row.get('monkey_exit_code', 'n/a')} | {str(row.get('timed_out', False)).lower()} | {row.get('crash_count', 0)} |"
        )
    return "\n".join(lines) + "\n"


def run_package_fuzz(adb_path: Path, serial: str, package: str, events: int, timeout_seconds: int, package_dir: Path, dry_run: bool):
    stdout_path = package_dir / "monkey.stdout.txt"
    stderr_path = package_dir / "monkey.stderr.txt"
    logcat_path = package_dir / "post_run_logcat.txt"
    crash_path = package_dir / "crash_lines.txt"

    if dry_run:
        write_text(stdout_path, f"DRY_RUN: would run monkey for {package} with {events} events and timeout {timeout_seconds}s\n")
        write_text(stderr_path, "")
        write_text(logcat_path, "DRY_RUN: logcat collection skipped\n")
        write_text(crash_path, "")
        return {
            "package": package,
            "status": "dry_run",
            "cause_category": "dry_run",
            "monkey_exit_code": 0,
            "timed_out": False,
            "dry_run": True,
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "logcat_path": str(logcat_path),
            "crash_lines": [],
            "crash_count": 0,
            "notes": "Dry-run mode: no actual monkey execution performed.",
        }

    clear_result = run_command([str(adb_path), "-s", serial, "logcat", "-c"], timeout=15)
    clear_failed = clear_result["returncode"] != 0

    monkey_cmd = [
        str(adb_path),
        "-s",
        serial,
        "shell",
        "monkey",
        "-p",
        package,
        "--throttle",
        "25",
        "--ignore-crashes",
        "--ignore-timeouts",
        "--ignore-security-exceptions",
        "--pct-syskeys",
        "0",
        "-v",
        "-v",
        str(events),
    ]
    monkey = run_command(monkey_cmd, timeout=timeout_seconds)
    write_text(stdout_path, monkey["stdout"])
    write_text(stderr_path, monkey["stderr"])

    logcat = run_command([str(adb_path), "-s", serial, "logcat", "-d", "-v", "brief"], timeout=30)
    write_text(logcat_path, logcat["stdout"])
    crash_lines = extract_crash_lines(logcat["stdout"], package)
    write_text(crash_path, "\n".join(crash_lines) + ("\n" if crash_lines else ""))

    adb_error = False
    adb_error_details = []
    if clear_failed:
        adb_error = True
        adb_error_details.append("pre_run_logcat_clear_failed")
    if logcat["returncode"] != 0:
        adb_error = True
        adb_error_details.append("post_run_logcat_dump_failed")

    if monkey["timed_out"]:
        status = "timed_out"
        cause = "timeout"
    elif adb_error:
        status = "completed_with_exit_code"
        cause = "adb_error"
    elif crash_lines:
        status = "crash_detected"
        cause = "monkey_crash_signal"
    elif monkey["returncode"] == 0:
        status = "completed"
        cause = "clean_exit"
    else:
        status = "completed_with_exit_code"
        cause = "monkey_nonzero_exit"

    return {
        "package": package,
        "status": status,
        "cause_category": cause,
        "monkey_exit_code": monkey["returncode"],
        "timed_out": monkey["timed_out"],
        "dry_run": False,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "logcat_path": str(logcat_path),
        "crash_lines": crash_lines,
        "crash_count": len(crash_lines),
        "adb_error_details": adb_error_details,
        "notes": "Monkey run completed and logcat crash extraction captured."
        if not clear_failed
        else "Monkey run completed; pre-run logcat clear failed, so cross-package noise may be present.",
    }


def validate_device(adb_path: Path, serial: str):
    state_cmd = [str(adb_path), "-s", serial, "get-state"]
    state_result = run_command(state_cmd, timeout=20)
    if state_result["timed_out"]:
        raise RuntimeError(f"adb {serial} get-state timed out")
    state = (state_result["stdout"] or state_result["stderr"] or "").strip().lower()
    if not state or state not in {"device", "ready"}:
        raise RuntimeError(f"device is offline or unavailable (state: {state or 'unknown'})")


def parse_args():
    parser = argparse.ArgumentParser(description="Run live APK fuzzing against a connected Android device using adb.")
    parser.add_argument("--adb-path", default=str(default_adb_path()), help="Path to adb.exe. Defaults to artifact-staging/tools/platform-tools/adb.exe")
    parser.add_argument("--serial", default="emulator-5580", help="Target device serial")
    parser.add_argument("--package-filter", default="flock", help="Substring filter for installed package names")
    parser.add_argument("--timeout-seconds", type=int, default=60, help="Per-package monkey timeout in seconds")
    parser.add_argument("--events", type=int, default=250, help="Monkey event count per package")
    parser.add_argument("--max-packages", type=int, default=0, help="Optional cap on packages to fuzz; 0 means no cap")
    parser.add_argument(
        "--flock-prefix",
        action="append",
        default=list(DEFAULT_FLOCK_PREFIXES),
        help="Allowed package prefix for Flock scope. Can be provided multiple times.",
    )
    parser.add_argument(
        "--flock-allowlist",
        action="append",
        default=list(DEFAULT_FLOCK_ALLOWLIST),
        help="Allowed exact package names for Flock scope. Can be provided multiple times.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Enumerate packages and emit dry-run results without launching monkey")
    parser.add_argument("--results-dir", default=str(repo_root() / "artifact-staging" / "results"), help="Directory to store summary files")
    return parser.parse_args()


def main():
    args = parse_args()
    adb_path = Path(args.adb_path).expanduser()
    if not adb_path.exists():
        print(f"[ERROR] adb not found at {adb_path}", file=sys.stderr)
        return 1

    version = run_command([str(adb_path), "version"], timeout=20)
    if version["returncode"] != 0:
        print(f"[ERROR] adb probe failed: {version['stderr'] or version['stdout'] or 'unknown adb error'}", file=sys.stderr)
        return 1

    try:
        validate_device(adb_path, args.serial)
    except RuntimeError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    try:
        packages = list_packages(adb_path, args.serial, args.package_filter)
    except RuntimeError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    if not packages:
        print(f"[ERROR] No installed packages matched filter '{args.package_filter}' on {args.serial}", file=sys.stderr)
        return 1

    allowed_prefixes, allowed_exact = normalize_scope_lists(args.flock_prefix, args.flock_allowlist)
    scoped_packages = []
    skipped_rows = []
    for package in packages:
        in_scope, scope_reason = is_flock_scoped_package(package, allowed_prefixes, allowed_exact)
        if in_scope:
            scoped_packages.append(package)
            continue
        skipped_rows.append(
            {
                "package": package,
                "status": "skipped",
                "cause_category": "skipped_non_flock",
                "monkey_exit_code": None,
                "timed_out": False,
                "dry_run": bool(args.dry_run),
                "stdout_path": None,
                "stderr_path": None,
                "logcat_path": None,
                "crash_lines": [],
                "crash_count": 0,
                "scope_reason": scope_reason,
                "notes": "Package matched filter but is outside enforced Flock scope.",
            }
        )

    if args.max_packages and args.max_packages > 0:
        scoped_packages = scoped_packages[: args.max_packages]

    results_dir = Path(args.results_dir)
    started_at = datetime.now(timezone.utc)
    timestamp = started_at.strftime("%Y%m%dT%H%M%S%z")
    run_dir = results_dir / f"live_fuzz_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    result_rows = list(skipped_rows)
    for package in scoped_packages:
        package_dir = run_dir / sanitize_name(package)
        result_rows.append(run_package_fuzz(adb_path, args.serial, package, args.events, args.timeout_seconds, package_dir, args.dry_run))

    cause_totals = {}
    for row in result_rows:
        cause = row.get("cause_category", "unknown")
        cause_totals[cause] = cause_totals.get(cause, 0) + 1

    summary = {
        "timestamp": started_at.isoformat(),
        "device": args.serial,
        "serial": args.serial,
        "package_filter": args.package_filter,
        "adb_path": str(adb_path),
        "adb_version_output": (version["stdout"] or version["stderr"] or "").strip(),
        "timeout_seconds": args.timeout_seconds,
        "monkey_events": args.events,
        "package_count": len(result_rows),
        "matched_package_count": len(packages),
        "fuzzed_package_count": len(scoped_packages),
        "skipped_package_count": len(skipped_rows),
        "allowed_flock_prefixes": allowed_prefixes,
        "allowed_flock_allowlist": allowed_exact,
        "cause_totals": cause_totals,
        "dry_run": bool(args.dry_run),
        "results": result_rows,
    }

    json_path = run_dir / "fuzz_summary.json"
    md_path = run_dir / "fuzz_summary.md"
    write_text(json_path, json.dumps(summary, indent=2) + "\n")
    write_text(md_path, build_markdown(summary))

    print(f"Summary JSON: {json_path}")
    print(f"Summary Markdown: {md_path}")
    print(build_markdown(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
