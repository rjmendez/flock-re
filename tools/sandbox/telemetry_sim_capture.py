#!/usr/bin/env python3
"""Collect/parse sandbox harness outputs into a telemetry training dataset."""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path
from typing import Any


def _now_id() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _discover_summaries(root: Path) -> list[Path]:
    return sorted(root.glob("client_harness_*/summary.json"))


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _collect_rows(summary_paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for summary_path in summary_paths:
        summary = _load_json(summary_path)
        run_dir = summary.get("run_dir", str(summary_path.parent))
        for item in summary.get("results", []):
            if not isinstance(item, dict):
                continue
            rows.append(
                {
                    "run_dir": str(run_dir),
                    "scenario": item.get("scenario"),
                    "expected_success": item.get("expected_success"),
                    "client_success": item.get("client_success"),
                    "client_returncode": item.get("client_returncode"),
                    "client_matches_expectation": item.get("client_matches_expectation"),
                    "continued_after_fail_ack": item.get("continued_after_fail_ack"),
                    "fail_ack_count": len(item.get("fail_acks_seen", []) or []),
                    "received_ops_count": len(item.get("received_ops", []) or []),
                }
            )
    return rows


def _apply_quality_gates(rows: list[dict[str, Any]], min_rows: int) -> tuple[list[dict[str, Any]], list[str]]:
    blockers: list[str] = []
    required_fields = [
        "run_dir",
        "scenario",
        "expected_success",
        "client_success",
        "client_returncode",
        "client_matches_expectation",
        "continued_after_fail_ack",
        "fail_ack_count",
        "received_ops_count",
    ]
    cleaned = []
    seen = set()
    for row in rows:
        if any(row.get(field) is None for field in required_fields):
            continue
        dedupe_key = (row["run_dir"], row["scenario"])
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        cleaned.append(row)

    if len(cleaned) < min_rows:
        blockers.append(f"rows_after_quality={len(cleaned)} below min_rows={min_rows}")
    if not cleaned:
        blockers.append("No valid telemetry rows after quality filtering.")
    return cleaned, blockers


def _write_outputs(out_dir: Path, rows: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "telemetry_rows.jsonl"
    csv_path = out_dir / "telemetry_rows.csv"
    manifest_path = out_dir / "collector_manifest.json"

    with jsonl_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")

    if rows:
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    else:
        csv_path.write_text("", encoding="utf-8")

    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote: {jsonl_path}")
    print(f"wrote: {csv_path}")
    print(f"wrote: {manifest_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["collect", "parse"], default="parse")
    parser.add_argument("--campaign-root", type=Path, default=Path("tools/sandbox/campaign_results"))
    parser.add_argument("--out-root", type=Path, default=Path("artifact-staging/results/telemetry_sim_capture"))
    parser.add_argument("--run-id", default="")
    parser.add_argument("--min-rows", type=int, default=6, help="Quality gate for minimum row count.")
    args = parser.parse_args()

    run_id = args.run_id or f"telemetry-sim-{_now_id()}"
    out_dir = args.out_root / run_id
    summary_paths = _discover_summaries(args.campaign_root)
    rows = _collect_rows(summary_paths)

    blockers: list[str] = []
    final_rows = rows
    if args.mode == "parse":
        final_rows, blockers = _apply_quality_gates(rows, max(1, args.min_rows))

    manifest = {
        "runner": "tools/sandbox/telemetry_sim_capture.py",
        "mode": args.mode,
        "run_id": run_id,
        "campaign_root": str(args.campaign_root),
        "summary_files_count": len(summary_paths),
        "rows_collected": len(rows),
        "rows_emitted": len(final_rows),
        "validation_ok": len(blockers) == 0,
        "blockers": blockers,
    }
    _write_outputs(out_dir, final_rows, manifest)
    return 0 if manifest["validation_ok"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
