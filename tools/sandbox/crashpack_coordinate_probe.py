#!/usr/bin/env python3
"""Scan unpacked crash-pack logs for likely GPS/coordinate evidence."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

COORD_PATTERNS = [
    re.compile(r"\b(?:latitude|lat)\s*[:=]\s*(-?\d{1,3}(?:\.\d+)?)", re.IGNORECASE),
    re.compile(r"\b(?:longitude|lon|lng)\s*[:=]\s*(-?\d{1,3}(?:\.\d+)?)", re.IGNORECASE),
    re.compile(r"\bgps\b", re.IGNORECASE),
]


def iter_files(root: Path):
    if root.is_file():
        yield root
        return
    for path in root.rglob('*'):
        if path.is_file():
            yield path


def collect_hits(path: Path, max_samples: int):
    samples = []
    hit_count = 0
    try:
        with path.open('r', encoding='utf-8', errors='replace') as handle:
            for idx, raw_line in enumerate(handle, start=1):
                line = raw_line.rstrip('\n')
                if any(p.search(line) for p in COORD_PATTERNS):
                    hit_count += 1
                    if len(samples) < max_samples:
                        samples.append({'line': idx, 'text': line[:300]})
    except OSError:
        return 0, []
    return hit_count, samples


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path, help='Unpacked crash-pack root or a single log file')
    parser.add_argument('--max-samples', type=int, default=3, help='Sample lines per file')
    parser.add_argument('--json', action='store_true', help='Output JSON')
    args = parser.parse_args()

    root = args.path
    if not root.exists():
        raise SystemExit(f'Path not found: {root}')

    results = []
    total_hits = 0
    ciroc_hits = 0

    for file_path in iter_files(root):
        hits, samples = collect_hits(file_path, args.max_samples)
        if not hits:
            continue
        rel = str(file_path.relative_to(root)) if root.is_dir() else file_path.name
        if 'ciroc' in rel.lower():
            ciroc_hits += hits
        total_hits += hits
        results.append({'file': rel, 'hits': hits, 'samples': samples})

    summary = {
        'scanned_root': str(root),
        'files_with_hits': len(results),
        'total_hits': total_hits,
        'ciroc_hits': ciroc_hits,
        'results': sorted(results, key=lambda r: r['hits'], reverse=True),
    }

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"Scanned: {summary['scanned_root']}")
        print(f"Files with coordinate-like hits: {summary['files_with_hits']}")
        print(f"Total coordinate-like hits: {summary['total_hits']}")
        print(f"Hits in ciroc files: {summary['ciroc_hits']}")
        for item in summary['results']:
            print(f"\n[{item['hits']:4d}] {item['file']}")
            for sample in item['samples']:
                print(f"  L{sample['line']}: {sample['text']}")

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
