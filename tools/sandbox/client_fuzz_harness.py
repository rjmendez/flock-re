#!/usr/bin/env python3
"""Client-side fuzz harness using a controllable localhost server emulator.

Runs upload_client.py against deterministic emulator scenarios and captures whether
the client properly handles malformed responses and state-transition failures.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
CLIENT_SCRIPT = SCRIPT_DIR / "upload_client.py"
EMULATOR_SCRIPT = SCRIPT_DIR / "client_server_emulator.py"
RESULT_ROOT = SCRIPT_DIR / "campaign_results"
TRACE_ARTIFACT_ROOT = SCRIPT_DIR.parent.parent / "artifact-staging" / "fail_ack_traces"


@dataclass(frozen=True)
class HarnessScenario:
    name: str
    expected_success: bool
    expected_behavior: str


SCENARIOS = [
    HarnessScenario("happy-path", True, "client should complete upload round-trip"),
    HarnessScenario("hello-truncated-response", False, "client should reject truncated HELLO response"),
    HarnessScenario("hello-close-no-response", False, "client should fail when HELLO response is missing"),
    HarnessScenario("metadata-fail-ack", False, "client should stop when METADATA ack is FAIL"),
    HarnessScenario("hash-fail-ack", False, "client should fail hash validation when HASH ack is FAIL"),
    HarnessScenario("session-close-fail", False, "client should stop when SESSION ack is FAIL"),
]


def _ts() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _run(cmd: list[str], timeout_s: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, check=False)


def _start_emulator(python_bin: str, scenario: str, report_path: Path, timeout_s: float) -> tuple[subprocess.Popen[str], int]:
    cmd = [
        python_bin,
        str(EMULATOR_SCRIPT),
        "--scenario",
        scenario,
        "--report",
        str(report_path),
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if not proc.stdout:
        raise RuntimeError("emulator stdout pipe unavailable")
    deadline = time.time() + timeout_s
    port = None
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                stderr = proc.stderr.read() if proc.stderr else ""
                raise RuntimeError(f"emulator exited early ({proc.returncode}): {stderr.strip()}")
            time.sleep(0.05)
            continue
        line = line.strip()
        if line.startswith("emulator-listening:"):
            port = int(line.split(":", 1)[1])
            break
    if port is None:
        proc.terminate()
        raise RuntimeError(f"timed out waiting for emulator port for scenario {scenario}")
    return proc, port


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _client_success(result: subprocess.CompletedProcess[str]) -> bool:
    if result.returncode != 0:
        return False
    return "upload round-trip OK" in result.stdout




def _write_fail_ack_trace(run_dir: Path, row: dict[str, Any], emulator_report: dict[str, Any]) -> None:
    """Write redacted fail-ack decision traces for provisional evidence tracking."""
    if not row.get("fail_acks_seen"):
        return
    trace = {
        "scenario": row["scenario"],
        "expected_success": row["expected_success"],
        "client_success": row["client_success"],
        "client_returncode": row["client_returncode"],
        "continued_after_fail_ack": row["continued_after_fail_ack"],
        "fail_acks_seen": row["fail_acks_seen"],
        "received_ops": row["received_ops"],
        "event_count": len(emulator_report.get("events", [])),
    }
    run_trace = run_dir / f"{row['scenario']}.fail-ack-trace.json"
    run_trace.write_text(json.dumps(trace, indent=2), encoding="utf-8")

    TRACE_ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    stable_trace = TRACE_ARTIFACT_ROOT / f"fail-ack-{row['scenario']}.json"
    stable_trace.write_text(json.dumps(trace, indent=2), encoding="utf-8")
def _result_row(
    scenario: HarnessScenario,
    client_result: subprocess.CompletedProcess[str],
    emulator_report: dict[str, Any],
) -> dict[str, Any]:
    success = _client_success(client_result)
    received_ops = emulator_report.get("received_ops", [])
    fail_acks = [
        evt.get("opcode_name")
        for evt in emulator_report.get("events", [])
        if evt.get("kind") == "opcode" and evt.get("ack") == 0
    ]
    continued_after_fail = False
    if fail_acks and received_ops:
        first_failed = fail_acks[0]
        if first_failed in received_ops:
            idx = received_ops.index(first_failed)
            continued_after_fail = idx < (len(received_ops) - 1)
    return {
        "scenario": scenario.name,
        "expected_success": scenario.expected_success,
        "expected_behavior": scenario.expected_behavior,
        "client_returncode": client_result.returncode,
        "client_success": success,
        "client_matches_expectation": success == scenario.expected_success,
        "fail_acks_seen": fail_acks,
        "continued_after_fail_ack": continued_after_fail,
        "received_ops": received_ops,
        "stdout_tail": client_result.stdout[-800:],
        "stderr_tail": client_result.stderr[-800:],
    }


def run_harness(args: argparse.Namespace) -> int:
    if not CLIENT_SCRIPT.is_file() or not EMULATOR_SCRIPT.is_file():
        raise SystemExit("missing upload_client.py or client_server_emulator.py")
    selected = {x.name: x for x in SCENARIOS}
    scenario_names = [args.scenario] if args.scenario else [x.name for x in SCENARIOS]
    run_dir = RESULT_ROOT / f"client_harness_{_ts()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for name in scenario_names:
        if name not in selected:
            raise SystemExit(f"unknown scenario: {name}")
        scenario = selected[name]
        report_path = run_dir / f"{name}.emulator.json"
        try:
            emu_proc, port = _start_emulator(args.python, name, report_path, args.start_timeout)
            client_cmd = [
                args.python,
                str(CLIENT_SCRIPT),
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--plaintext",
                "--token",
                "SANDBOX-FAKE-TOKEN",
                "--size",
                str(args.size),
            ]
            client_result = _run(client_cmd, args.client_timeout)
        finally:
            if "emu_proc" in locals() and emu_proc.poll() is None:
                emu_proc.terminate()
                try:
                    emu_proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    emu_proc.kill()
                    emu_proc.wait(timeout=3)
        emulator_report = _load_json(report_path)
        row = _result_row(scenario, client_result, emulator_report)
        rows.append(row)
        _write_fail_ack_trace(run_dir, row, emulator_report)
        verdict = "PASS" if row["client_matches_expectation"] else "MISMATCH"
        print(f"[{verdict}] {name} rc={row['client_returncode']} client_success={row['client_success']}")
        if row["continued_after_fail_ack"]:
            print(f"  note: client continued after FAIL ack in {name}")

    summary = {
        "run_dir": str(run_dir),
        "scenario_count": len(rows),
        "matched_expectations": sum(1 for x in rows if x["client_matches_expectation"]),
        "mismatches": [x["scenario"] for x in rows if not x["client_matches_expectation"]],
        "continued_after_fail_ack": [x["scenario"] for x in rows if x["continued_after_fail_ack"]],
        "results": rows,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"wrote: {run_dir / 'summary.json'}")
    if summary["mismatches"]:
        print("mismatch scenarios:", ", ".join(summary["mismatches"]))
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable, help="Python interpreter")
    parser.add_argument("--scenario", default=None, help="Run a single scenario")
    parser.add_argument("--size", type=int, default=4096, help="Synthetic upload size for client")
    parser.add_argument("--start-timeout", type=float, default=5.0)
    parser.add_argument("--client-timeout", type=float, default=12.0)
    return parser


def main() -> int:
    return run_harness(build_parser().parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
