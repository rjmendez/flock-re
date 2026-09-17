# Crash logs (crash packs)

Inside the encrypted media volume, under `/media/0/media/crashpack/`, sit gzipped
diagnostic bundles (`.pak`). Because they live in the [encrypted `android_expand`
volume](data-and-storage.md), they're only readable after decrypting with the
colocated key — likely why they were previously unexamined.

## What they are
- Each `.pak` is a **gzip → tar of ~200 runtime log files** (one sampled pack: 68 MiB
  gzipped → **773 MiB** uncompressed, 201 members).
- Contents: one log per app (`objects`, `ciroc`, `cachaca`, `uploadclient`,
  `phonehomeservice`, `sambuca`, `peripheral`, `cameraupdater`, `encoding`,
  `bigboibud`, `medallalight`, `validator`, `qualitycontrol`, …), plus
  `logcat_kernel`, `logcat_radio`, `modemInfo.txt`, and `rescue-level-by-apps.txt`.

## Why they matter
- **Secrets in plaintext logs.** The app logs contain a **bearer token** and
  **password** strings in the clear (values redacted here) — credentials leaking into
  diagnostics that then ship inside the capture store.
- **Cell-tower identifiers.** `modemInfo.txt` records the live LTE serving cell
  (`cid`, `tac`, `pci`, `earfcn`, signal levels) and the Sierra Wireless baseband
  version. Tower IDs are **region-derivable** via a cell-tower database — no GPS needed.
- **Backend chatter.** Two `*.flocksafety.com` hosts dominate (tens of thousands of
  hits), confirming the [backend endpoints](backend-protocol.md).
- **Self-recovery.** `rescue-level-by-apps.txt` logs repeated "Rescue Level 1" events —
  the watchdog restart pattern (see [Kernel & drivers](kernel.md)).
- **No GPS in logs** — location isn't logged as lat/lon; the geotag stays out-of-band.

## See also
- [Data & storage](data-and-storage.md) · [Security posture](security-posture.md) · [Backend protocol](backend-protocol.md)
