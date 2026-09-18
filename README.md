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
- **`workflow/flock-simulated-red-team.js`** — authorization-gated dynamic assessment
  of an owned simulation across internet/control-plane, LAN/Wi-Fi, radio, optical,
  accessory/debug, physical/storage, on-device IPC, and operational layers. Uses the
  Loci swarm for hypotheses, then requires independent evidence for every finding.

The `workflow/*.js` scripts run with the Claude Code Workflow tool. The firmware-analysis
workflows let anyone with the public dump **reproduce and verify** the static findings;
edit their CONFIG blocks or pass paths/model tags via `args`. The simulated red-team
workflow instead requires an owned simulation and permits bounded dynamic tests only
against targets explicitly allowlisted by its authorization gate. It rejects vendor
domains and public targets by default.
