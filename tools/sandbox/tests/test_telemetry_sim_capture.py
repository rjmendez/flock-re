import json
from pathlib import Path

from tools.sandbox import telemetry_sim_capture as cap


def _write_summary(path: Path, run_dir: str, scenario: str):
    payload = {
        "run_dir": run_dir,
        "results": [
            {
                "scenario": scenario,
                "expected_success": True,
                "client_success": True,
                "client_returncode": 0,
                "client_matches_expectation": True,
                "continued_after_fail_ack": False,
                "fail_acks_seen": [],
                "received_ops": ["HELLO", "METADATA"],
            }
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_collect_rows_from_harness_summaries(tmp_path):
    root = tmp_path / "campaign_results"
    _write_summary(root / "client_harness_1" / "summary.json", "r1", "happy-path")
    rows = cap._collect_rows(cap._discover_summaries(root))
    assert len(rows) == 1
    assert rows[0]["scenario"] == "happy-path"
    assert rows[0]["received_ops_count"] == 2


def test_quality_gate_blocks_when_insufficient_rows():
    rows = [{"run_dir": "r", "scenario": "s"}]
    cleaned, blockers = cap._apply_quality_gates(rows, min_rows=2)
    assert cleaned == []
    assert blockers
