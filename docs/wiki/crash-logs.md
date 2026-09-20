# Crash logs (crash packs)

Inside the encrypted media volume, under `/media/0/media/crashpack/`, sit gzipped diagnostic
bundles (`.pak`). They only decrypt with the [colocated key](data-and-storage.md), which is
likely why their **contents** were previously unexamined (the *existence* of the mechanism —
an unauthenticated `/crashpack` endpoint on port 8080 — is public as CVE-2025-59403, but no
public writeup walks an actual pack's logs).

## What they are
Four packs in this dump (68–~75 MiB gzip each → **~1.9 GiB total** uncompressed), each a
**tar of per-app runtime logs** (12–204 files per pack, 488 total):

| Pack date | gzip | uncompressed | logs |
|---|---|---|---|
| 2025-07-23 (a) | 68 MiB | 773 MiB | 201 |
| 2025-07-23 (b) | — | 39 MiB | 12 |
| 2025-08-19 | ~75 MiB | 860 MiB | 204 |
| 2026-01-28 | — | 231 MiB | 71 |

Contents: one log per app (`objects`, `ciroc`, `cachaca`, `encoding`, `uploadclient`,
`phonehomeservice`, `sambuca`, `peripheral`, `bigboibud`, `medallalight`, `validator`,
`qualitycontrol`), plus `logcat_kernel`, `logcat_radio`, `modemInfo.txt`, `rescue-level-by-apps.txt`.

## What the logs reveal (redacted)
- **A static upload credential in cleartext.** A per-device client-auth token (UUID) that
  authenticates every media-upload connection is logged **in full, ~3,906 times** across 6+
  months at ordinary log level — so it ships in every crash pack. Unchanged the whole span.
  (New — not in any public report.) See [Security posture](security-posture.md).
- **Whole network surface = 3 hosts.** Two REST APIs (legacy v1 + v4) used by
  `phonehomeservice`, plus one raw-TLS binary-upload socket (`ConnectionClient`). A ~36.5 KB
  telemetry/status payload posts every cycle; the backend self-reports ~1,950 internal pod IPs.
  See [Backend protocol](backend-protocol.md).
- **Cell-tower identifiers.** `modemInfo.txt` records the serving LTE cell (`cid`/`tac`/`pci`/
  `earfcn`, signal) and the Sierra Wireless baseband — region-derivable, no GPS needed.
- **Self-recovery.** `rescue-level-by-apps.txt` logs repeated "Rescue Level 1" watchdog events.
- **No bearer/OAuth-header leaks observed** beyond the static upload token.

## Coordinate evidence status (important correction)
- Earlier revisions of this page stated "**No GPS in logs**." That is now treated as
  **unresolved**, not established fact.
- Repo evidence already shows GPS fields in transmitted models/payloads (see
  [Backend protocol](backend-protocol.md)); an external blog-mapped report additionally
  claims explicit latitude/longitude values in `ciroc` crash-pack logs.
- Because this repo has not yet published line-level excerpts of those exact `ciroc` log
  coordinate entries, this page now tracks it as a **verification gap** rather than
  asserting either side as final truth.

### Repro path for this gap
After decrypting and unpacking crash packs, run:

```bash
python3 tools/sandbox/crashpack_coordinate_probe.py /path/to/unpacked/crashpack
```

This surfaces likely coordinate-bearing lines (`latitude`, `longitude`, `lat=`, `lon=`,
`gps`) with per-file hit counts and samples so the `ciroc`-GPS claim can be confirmed or
refuted with publishable evidence.

## See also
- [Data & storage](data-and-storage.md) · [Security posture](security-posture.md) · [Backend protocol](backend-protocol.md) · [Prior work](prior-work.md)
