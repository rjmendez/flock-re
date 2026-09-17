# Tools

Two parts: the code written for this project (in this repo), and the third-party tools you
install yourself to reproduce the extraction. **No third-party binaries are vendored here** —
just install docs.

## Code in this repo

- **`tools/download/bt.py`** — libtorrent fetcher for the public dump (resumable, web-seed
  fallback, piece-hash verification).
- **`workflow/flock-firmware-peel.js`** — first-pass extraction workflow (partition extract +
  decompile).
- **`workflow/flock-deep-static-re.js`**, **`workflow/flock-deeper-everything.js`** — the deeper
  static-RE passes. Run with the Claude Code Workflow tool; static/offline by construction.

Everything else below is standard, publicly available tooling — install it and point the
workflows/commands at the dump.

## Third-party tools to install

User-level installs (no root needed). Versions are what this analysis used; newer usually works.

| Tool | Version | Install (user-level) | Used for |
|---|---|---|---|
| **jadx** | 1.5.6 | Download release zip from `github.com/skylot/jadx/releases`, unzip | Decompile the app APKs → Java/Kotlin |
| **Ghidra** | 12.1.3 | Download from `github.com/NationalSecurityAgency/ghidra/releases`, unzip (needs JDK 17+) | Decompile native `.so` libs (`analyzeHeadless`) |
| **radare2** | 6.2.x | `github.com/radareorg/radare2` installer, or distro package | Disassembly / triage of ELF binaries |
| **binwalk** | 2.3.4 (classic) | `pip install --user 'git+https://github.com/ReFirmLabs/binwalk.git@v2.3.4'` (Python 3.11 venv) | Signature scan / carve Qualcomm blobs |
| **android-simg2img** | anestisb/master | `curl -L` the repo tarball, `tar xzf`, `make` | Convert Android sparse images → raw (if present) |
| **unpack_bootimg.py** | AOSP mkbootimg | Fetch from `android.googlesource.com/platform/system/tools/mkbootimg` | Split `boot`/`recovery` → kernel + ramdisk |
| **7-Zip (7zz)** | 26.x | Static build from `github.com/ip7z/7zip/releases` | List/extract ext4 trees (`7z l` / `7z x`) |
| **e2fsprogs (debugfs)** | 1.47 | usually preinstalled; else distro package | Read-only ext4 extraction (`debugfs -R 'rdump / <dst>'`) |
| **sqlite3** | any | usually preinstalled | Dump DB schemas (`.schema`) — schema only |
| **Python: tflite / flatbuffers** | any | `pip install --user tflite flatbuffers` | Parse the on-device `.tflite` models |
| **file, cpio, lz4, gzip** | any | usually preinstalled | ramdisk/format handling |

### Notes / gotchas
- The PyPI `binwalk` package (2.1.0) is a **broken stub** — use the classic v2.3.4 from git as
  shown, or the Rust binwalk v3 if you can satisfy its build deps.
- No PyPI `simg2img` exists; build anestisb's from source. This particular dump is raw (not
  sparse), so simg2img isn't strictly needed for it.
- Ghidra and jadx both need a JDK (17+); JDK 21 works.
- Always operate **read-only** on the partition images (e.g. `debugfs` without `-w`), and never
  extract captured media/personal records — schemas/structure only.

## Reproduce
1. `python3 tools/download/bt.py` → fetch the dump.
2. Install the tools above.
3. Run the workflows (Workflow tool), or invoke the tools directly per the commands in the table.
