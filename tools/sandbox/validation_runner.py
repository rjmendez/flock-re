#!/usr/bin/env python3
"""Default sandbox validation runner.

Runs core local validation checks and writes redacted summary artifacts.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
ARTIFACT_DIR = REPO_ROOT / "artifact-staging" / "results"


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True, check=False)


def _extract_summary_path(output: str) -> str:
    summary = ""
    for line in output.splitlines():
        if line.startswith("wrote: ") and line.strip().endswith("summary.json"):
            summary = line.split("wrote: ", 1)[1].strip()
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--python", default=sys.executable, help="Python interpreter")
    args = ap.parse_args()

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    harness_cmd = [args.python, str(SCRIPT_DIR / "client_fuzz_harness.py") ]
    pytest_cmd = [args.python, "-m", "pytest", "-q", "tools/sandbox/tests/test_upload_server_hardening.py"]

    harness = _run(harness_cmd)
    pytest_res = _run(pytest_cmd)

    harness_summary_path = _extract_summary_path(harness.stdout)
    harness_summary = {}
    if harness_summary_path:
        p = Path(harness_summary_path)
        if p.is_file():
            harness_summary = json.loads(p.read_text(encoding="utf-8"))

    payload = {
        "runner": "tools/sandbox/validation_runner.py",
        "commands": {
            "client_fuzz_harness": {"cmd": harness_cmd, "returncode": harness.returncode},
            "upload_server_hardening_pytest": {"cmd": pytest_cmd, "returncode": pytest_res.returncode},
        },
        "harness": {
            "summary_json": harness_summary_path,
            "scenario_count": harness_summary.get("scenario_count"),
            "matched_expectations": harness_summary.get("matched_expectations"),
            "mismatches": harness_summary.get("mismatches", []),
            "continued_after_fail_ack": harness_summary.get("continued_after_fail_ack", []),
        },
        "pytest_stdout_tail": pytest_res.stdout[-1500:],
        "status": "pass" if harness.returncode == 0 and pytest_res.returncode == 0 else "fail"
    }

    json_out = ARTIFACT_DIR / "sandbox_validation_summary_redacted.json"
    md_out = ARTIFACT_DIR / "sandbox_validation_summary_redacted.md"
    json_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md = [
        "# Sandbox validation summary (redacted)",
        "",
        f"- Overall status: **{payload['status']}**",
        f"- Harness return code: **{harness.returncode}**",
        f"- Pytest return code: **{pytest_res.returncode}**",
        "",
        "## Harness",
        f"- summary json: `{harness_summary_path or 'unavailable'}`",
        f"- scenarios: `{payload['harness']['matched_expectations']}` / `{payload['harness']['scenario_count']}` matched",
        f"- mismatches: `{', '.join(payload['harness']['mismatches']) or 'none'}`",
        f"- continued after fail-ack: `{', '.join(payload['harness']['continued_after_fail_ack']) or 'none'}`",
        "",
        "## Pytest",
        "```",
        payload["pytest_stdout_tail"].strip(),
        "```",
    ]
    md_out.write_text('\n'.join(md) + '\n', encoding="utf-8")

    print(f"wrote: {json_out}")
    print(f"wrote: {md_out}")

    if payload["status"] != "pass":
        print("validation runner detected failures/mismatches", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
