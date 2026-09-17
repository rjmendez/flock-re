# Methodology

## 1. Acquisition

`tools/download/bt.py` — libtorrent client (user venv, no root). Adds
`data.ddosecrets.org` as a web-seed since the torrent ships none, keeps a
`heartbeat`, saves fastresume, and verifies every piece hash before reporting
complete. Resumable across restarts via hash-recheck of on-disk data.

## 2. Peel workflow

`workflow/flock-firmware-peel.js` — a multi-agent workflow:

1. **Recon & Setup** (parallel): device intel + user-level install of binwalk,
   simg2img, a boot-img unpacker, and Ghidra (JDK 21 already present).
2. **Extract** (5 parallel agents, each owning a distinct output dir):
   boot/kernel, Android FS (system/vendor/oem/persist), Qualcomm blobs
   (modem/tz/aboot), secrets/identity, data partitions.
3. **Analyze**: first-pass RE of the ALPR app + native libs with radare2 and
   Ghidra headless.

Agents operate read-only on the images so acquisition/seeding is undisturbed.
Secrets are written to local-only files and returned redacted.

## 3. Adversarial layer (local abliterated models)

`adversarial/redteam_local.py` runs RE findings through the local, GPU-backed,
uncensored ("heretic"/abliterated) models for offensive-security reasoning that
hosted models tend to hedge on:

- **red-team**: given the device architecture, endpoints, and creds, enumerate
  concrete attack paths without safety hedging.
- **refute**: adversarially challenge each finding; majority-refute drops it.
- **gaps**: what did the primary analysis miss or self-censor?

Models live on this machine's Windows Ollama (`100.73.200.19:11434`, reachable
from WSL only via the Tailscale IP). Default `Qwen3.8-27B-Heretic` for
load-bearing work; smaller heretic models for cheap fan-out. Also reachable
through Loci: `mcp__loci__llm_local` and the `mcp__loci__swarm_reason`
deep-think swarm (point its model params at heretic tags).

Caveats: small (≤8B) models hallucinate and over-refute; treat their output as
leads to verify, not conclusions. Prefer the 27B; keep_alive long to avoid the
~70s cold load.
