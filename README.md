# flock-re

Tooling for reverse-engineering a Flock Safety ALPR camera firmware dump
(Qualcomm Snapdragon / Android), from the public DDoSecrets release.

Tools only. Raw dumps, extracted filesystems, captured media, and any secrets
stay untracked — see `.gitignore`.

## Docs

[`docs/wiki/`](docs/wiki/Home.md) — a cross-linked wiki on the firmware's structure
(hardware, partitions, boot, apps, ALPR pipeline, backend protocol, security posture)
plus a [claims-vs-evidence](docs/wiki/claims-vs-evidence.md) page testing Flock's public
statements against the firmware. Hostnames and secrets are obfuscated.

Documentation standard: narrative analysis belongs in `docs/wiki/`; raw runtime evidence
(logs/JSON command outputs) belongs in `tools/*/campaign_results/` or equivalent artifact
directories. Avoid publishing process/tool provenance notes.

## Tools

- **`tools/download/bt.py`** — libtorrent fetcher for the dump. Resumable, adds a
  web-seed fallback, verifies piece hashes.
- **`tools/modeltest/detect.py`** — runs an extracted `.tflite` detector on your own
  synthetic/public images (never captured data) to characterize what it detects and at
  what confidence. See `tools/modeltest/README.md`.
- **`tools/schema/extract_capture_schema.sh`** — reproduces the on-device capture-record
  schema findings (no plate-text column, detection geometry/class only, no GPS/IMU) from
  a directory of jadx-decompiled sources. Static, offline, read-only.
