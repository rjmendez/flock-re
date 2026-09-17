# flock-re

Reverse-engineering tooling and notes for a Flock Safety ALPR camera firmware dump
(Qualcomm Snapdragon / Android). Source dump: the DDoSecrets "Flock ALPR camera"
release (~28.6 GiB, 54 partitions).

This repo holds **tools, scripts, and documentation only**. Raw dumps, extracted
filesystems, captured media, and any secret values are deliberately kept out of
version control (see `.gitignore`) — they are large, re-derivable, and contain PII.

## Layout

```
tools/download/    torrent fetcher (libtorrent, resumable, web-seed fallback)
tools/extract/     partition extraction / carving helpers
workflow/          the multi-agent RE workflow script (flock-firmware-peel.js)
adversarial/       local abliterated-model red-team / refutation harness
docs/              device profile, methodology, findings write-ups
```

## Data location (not tracked)

The raw dump lives outside this repo at `~/flock-alpr/Flock ALPR camera/`
(`paritions/` — the leak's own spelling — plus `sample-media/` and
`partitions.csv`). Extraction output goes to `~/flock-alpr/re/`.

## Getting the dump

```
python3 tools/download/bt.py     # needs libtorrent in a venv; resumable, verifies piece hashes
```

## Scope / ethics

Analysis of an already-public leak of a mass-surveillance device, for security
research. Extracted credentials and any captured plate imagery / personal records
are treated as sensitive: secrets are written to local-only files and never
committed; captured media is characterized in aggregate (counts, schemas), not
copied or redistributed.
