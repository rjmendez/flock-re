#!/usr/bin/env python3
"""Guard against committing generated artifact output that stays local-only."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import PurePosixPath

BLOCKED_PREFIXES = (
    'artifact-staging',
    'tools/sandbox/campaign_results',
    'tools/sandbox/honggfuzz/runtime',
)


def normalize_repo_relative(path: str, repo_root: str | None = None) -> str:
    """Normalize a repo-relative path for comparison, including Windows separators."""
    if not path:
        return ''

    cleaned = path.strip().replace(chr(92), '/')
    while cleaned.startswith('./'):
        cleaned = cleaned[2:]
    while cleaned.startswith('/'):
        cleaned = cleaned[1:]

    if repo_root and os.path.isabs(path):
        try:
            rel = os.path.relpath(path, repo_root)
            if rel != '.':
                cleaned = rel.replace(chr(92), '/')
        except ValueError:
            pass

    while cleaned.startswith('./'):
        cleaned = cleaned[2:]
    while cleaned.startswith('/'):
        cleaned = cleaned[1:]
    return cleaned


def is_blocked(path: str, repo_root: str | None = None) -> bool:
    cleaned = normalize_repo_relative(path, repo_root)
    if not cleaned:
        return False

    parts = PurePosixPath(cleaned).parts
    for prefix in BLOCKED_PREFIXES:
        if cleaned == prefix or cleaned.startswith(f'{prefix}/'):
            return True

    if len(parts) >= 3 and parts[0] == 'tools' and parts[1] == 'sandbox':
        if parts[2] == 'campaign_results':
            return True
        if parts[2] == 'honggfuzz' and len(parts) >= 4 and parts[3] == 'runtime':
            return True

    if len(parts) >= 4 and parts[:3] == ('tools', 'sandbox', 'honggfuzz') and parts[3] == 'runtime':
        return True

    return False


def collect_staged_paths(repo_root: str) -> list[str]:
    try:
        result = subprocess.run(
            ['git', '-C', repo_root, 'diff', '--cached', '--name-only', '--diff-filter=ACMR', '--relative'],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []

    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='*', help='Repository-relative file paths to check.')
    parser.add_argument('--repo-root', default='.', help='Repository root for resolving paths.')
    parser.add_argument('--staged', action='store_true', help='Check staged files instead of the explicit path list.')
    args = parser.parse_args()

    repo_root = os.path.abspath(args.repo_root)
    candidates: list[str] = []

    if args.staged:
        candidates = collect_staged_paths(repo_root)
    elif args.paths:
        candidates = args.paths
    else:
        candidates = collect_staged_paths(repo_root)

    blocked = [path for path in candidates if is_blocked(path, repo_root)]
    if blocked:
        print('Artifact guard blocked commit for the following paths:', file=sys.stderr)
        for path in blocked:
            print(f'  - {path}', file=sys.stderr)
        print('\nMove these files out of local-only artifact paths before committing.', file=sys.stderr)
        return 1

    if args.staged or args.paths:
        print('Artifact guard passed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
