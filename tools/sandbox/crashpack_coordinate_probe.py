#!/usr/bin/env python3
"""Scan unpacked crash-pack logs for likely GPS/coordinate evidence."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

COORD_PATTERNS = [
    re.compile(r"\b(?:latitude|lat)\s*[:=]\s*(-?\d{1,3}(?:\.\d+)?)", re.IGNORECASE),
    re.compile(r"\b(?:longitude|lon|lng)\s*[:=]\s*(-?\d{1,3}(?:\.\d+)?)", re.IGNORECASE),
    re.compile(r"\bgps\b", re.IGNORECASE),
]


def _is_within_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def iter_files(root: Path):
    root = root.resolve(strict=True)

    if root.is_file():
        if not root.is_symlink():
            yield root
        return

    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if not (Path(dirpath) / d).is_symlink())
        for filename in sorted(filenames):
            candidate = Path(dirpath) / filename
            if candidate.is_symlink():
                continue
            try:
                resolved = candidate.resolve(strict=True)
            except OSError:
                continue
            if not resolved.is_file() or not _is_within_root(resolved, root):
                continue
            yield candidate


def collect_hits(path: Path, max_samples: int):
    samples = []
    hit_count = 0
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for idx, raw_line in enumerate(handle, start=1):
                line = raw_line.rstrip("\n")
                if any(p.search(line) for p in COORD_PATTERNS):
                    hit_count += 1
                    if len(samples) < max_samples:
                        samples.append({"line": idx, "text": line[:300]})
    except OSError as exc:
        return 0, [], f"Read error for {path}: {exc}"
    return hit_count, samples, None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Unpacked crash-pack root or a single log file")
    parser.add_argument("--max-samples", type=int, default=3, help="Sample lines per file")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    root = args.path
    if not root.exists():
        raise SystemExit(f"Path not found: {root}")

    results = []
    total_hits = 0
    ciroc_hits = 0
    diagnostics = []

    for file_path in iter_files(root):
        hits, samples, diagnostic = collect_hits(file_path, args.max_samples)
        if diagnostic:
            diagnostics.append(diagnostic)
        if not hits:
            continue
        rel = str(file_path.relative_to(root)) if root.is_dir() else file_path.name
        if "ciroc" in rel.lower():
            ciroc_hits += hits
        total_hits += hits
        results.append({"file": rel, "hits": hits, "samples": samples})

    summary = {
        "scanned_root": str(root),
        "files_with_hits": len(results),
        "total_hits": total_hits,
        "ciroc_hits": ciroc_hits,
        "diagnostics": diagnostics,
        "results": sorted(results, key=lambda r: r["hits"], reverse=True),
    }

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"Scanned: {summary['scanned_root']}")
        print(f"Files with coordinate-like hits: {summary['files_with_hits']}")
        print(f"Total coordinate-like hits: {summary['total_hits']}")
        print(f"Hits in ciroc files: {summary['ciroc_hits']}")
        if diagnostics:
            print("Warnings:")
            for diagnostic in diagnostics:
                print(f"  - {diagnostic}")
        for item in summary["results"]:
            print(f"\n[{item['hits']:4d}] {item['file']}")
            for sample in item["samples"]:
                print(f"  L{sample['line']}: {sample['text']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())