#!/usr/bin/env python3
"""Quality-gate endpoint host extraction before claiming endpoint-map coverage."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HOST_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}(?::\d{1,5})?$",
    re.IGNORECASE,
)
COMMON_GTLDS = {
    "com",
    "org",
    "net",
    "edu",
    "gov",
    "mil",
    "io",
    "app",
    "dev",
    "cloud",
    "ai",
    "co",
    "me",
    "biz",
    "info",
}


def _normalize_host(token: str) -> str:
    return token.strip().lower().rstrip(".")


def _is_valid_host(token: str) -> bool:
    if not HOST_RE.fullmatch(token):
        return False
    host_only = token.rsplit(":", 1)[0]
    if "." not in host_only:
        return False
    tld = host_only.split(".")[-1]
    return len(tld) == 2 or tld in COMMON_GTLDS


def _load_top_hosts(path: Path) -> list[tuple[str, int]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    top = payload.get("global", {}).get("endpoint_hosts_top", [])
    rows: list[tuple[str, int]] = []
    for item in top:
        if not isinstance(item, list) or len(item) != 2:
            continue
        host, count = item
        if not isinstance(host, str) or not isinstance(count, int):
            continue
        rows.append((_normalize_host(host), count))
    return rows


def _assess(rows: list[tuple[str, int]]) -> dict[str, object]:
    total_weight = sum(count for _, count in rows)
    valid_rows = [(host, count) for host, count in rows if _is_valid_host(host)]
    uncertain_rows = [(host, count) for host, count in rows if not _is_valid_host(host)]
    valid_weight = sum(count for _, count in valid_rows)
    uncertain_weight = sum(count for _, count in uncertain_rows)
    valid_ratio = (valid_weight / total_weight) if total_weight else 0.0
    uncertain_ratio = (uncertain_weight / total_weight) if total_weight else 1.0
    return {
        "top_hosts_total": len(rows),
        "top_hosts_valid": len(valid_rows),
        "top_hosts_uncertain": len(uncertain_rows),
        "weighted_total": total_weight,
        "weighted_valid": valid_weight,
        "weighted_uncertain": uncertain_weight,
        "valid_domain_ratio": round(valid_ratio, 6),
        "uncertain_token_ratio": round(uncertain_ratio, 6),
        "high_confidence_hosts": sorted(valid_rows, key=lambda x: x[1], reverse=True),
        "uncertain_hosts": sorted(uncertain_rows, key=lambda x: x[1], reverse=True),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--analysis-json",
        type=Path,
        required=True,
        help="Path to full_crashpack_analysis.json containing global.endpoint_hosts_top.",
    )
    parser.add_argument("--min-valid-domain-ratio", type=float, default=0.80)
    parser.add_argument("--max-uncertain-token-ratio", type=float, default=0.20)
    parser.add_argument("--min-high-confidence-hosts", type=int, default=3)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()

    if not args.analysis_json.is_file():
        print(f"missing analysis file: {args.analysis_json}", file=sys.stderr)
        return 2

    rows = _load_top_hosts(args.analysis_json)
    assessment = _assess(rows)
    blockers: list[str] = []
    if assessment["top_hosts_total"] == 0:
        blockers.append("No endpoint host candidates found in analysis payload.")
    if assessment["valid_domain_ratio"] < args.min_valid_domain_ratio:
        blockers.append(
            f"valid_domain_ratio={assessment['valid_domain_ratio']} below threshold {args.min_valid_domain_ratio}"
        )
    if assessment["uncertain_token_ratio"] > args.max_uncertain_token_ratio:
        blockers.append(
            f"uncertain_token_ratio={assessment['uncertain_token_ratio']} above threshold {args.max_uncertain_token_ratio}"
        )
    if assessment["top_hosts_valid"] < args.min_high_confidence_hosts:
        blockers.append(
            f"high_confidence_hosts={assessment['top_hosts_valid']} below minimum {args.min_high_confidence_hosts}"
        )

    result = {
        "ok": len(blockers) == 0,
        "blocked": len(blockers) > 0,
        "analysis_json": str(args.analysis_json),
        "thresholds": {
            "min_valid_domain_ratio": args.min_valid_domain_ratio,
            "max_uncertain_token_ratio": args.max_uncertain_token_ratio,
            "min_high_confidence_hosts": args.min_high_confidence_hosts,
        },
        "assessment": assessment,
        "blockers": blockers,
    }
    output = json.dumps(result, indent=2)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(output + "\n", encoding="utf-8")
        print(f"wrote: {args.json_out}")
    else:
        print(output)

    return 0 if result["ok"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
