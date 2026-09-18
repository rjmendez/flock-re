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

## Tools

- **`tools/download/bt.py`** — libtorrent fetcher for the dump. Resumable, adds a
  web-seed fallback, verifies piece hashes.
- **`tools/modeltest/detect.py`** — runs an extracted `.tflite` detector on your own
  synthetic/public images (never captured data) to characterize what it detects and at
  what confidence. See `tools/modeltest/README.md`.
- **`tools/schema/extract_capture_schema.sh`** — reproduces the on-device capture-record
  schema findings (no plate-text column, detection geometry/class only, no GPS/IMU) from
  a directory of jadx-decompiled sources. Static, offline, read-only.
- **`workflow/flock-firmware-peel.js`** — multi-agent workflow: installs the
  toolchain, extracts the partitions in parallel, runs a first-pass decompile.
- **`workflow/flock-deep-static-re.js`** — deeper static RE across 8 subsystems
  (apk/dex, native ML, boot/secure-world, modem, persist/userdata, tflite, ipc,
  protocol) with local-model review. Static and offline.
- **`workflow/flock-deeper-everything.js`** — second-stage deeper pass (userdata/
  media crypto, remaining apps, kernel, OTA, camera, oem/dsp) + a cross-link graph
  spec. Never extracts captured media/personal records.

The three `workflow/*.js` scripts run with the Claude Code Workflow tool and let anyone
with the public dump **reproduce and verify** the findings. Edit the CONFIG block at the
top of each (paths, local model tags) or pass them via `args`. The deep passes are static
and offline by construction — they never contact a live system or use any credential.
