# flock-re

Tooling for reverse-engineering a Flock Safety ALPR camera firmware dump
(Qualcomm Snapdragon / Android), from the public DDoSecrets release.

Tools only. Raw dumps, extracted filesystems, captured media, and any secrets
stay untracked — see `.gitignore`.

## Tools

- **`tools/download/bt.py`** — libtorrent fetcher for the dump. Resumable, adds a
  web-seed fallback, verifies piece hashes.
- **`workflow/flock-firmware-peel.js`** — multi-agent workflow: installs the
  toolchain, extracts the partitions in parallel, runs a first-pass decompile.
- **`adversarial/redteam_local.py`** — runs RE findings through a local
  abliterated model (`redteam` / `refute` / `gaps` modes). Set `OLLAMA_GEN_URL`.
