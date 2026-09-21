# AFL++ / Frida scaffold for ARM32 native fuzzing

This directory bootstraps a **tier-2 AFL++ Frida-mode** starting point for the
Android ARM32 native layer, with the first target path aimed at
`libnativeImageUtils.so`-style **non-JNI** code.

The goal is practical and reproducible:

- prepare a self-contained workspace with explicit input/output directories,
- build a tiny Android ARM32 harness that loads the target `.so`,
- run that harness under AFL++ Frida mode with a pinned Frida pairing,
- keep the input contract small and explicit so the first corpus is easy to seed.

## What the harness expects

The harness reads a single binary testcase with this layout:

| Offset | Size | Meaning |
|---|---:|---|
| 0x00 | 4 | ASCII magic `FIMU` |
| 0x04 | 1 | format version, currently `1` |
| 0x05 | 1 | call mode (`0` = raw buffer, `1` = image-frame adapter) |
| 0x06 | 1 | pixel format (`0` = NV21, `1` = YUV420P, `2` = RGBA8888) |
| 0x07 | 1 | reserved |
| 0x08 | 4 | width, little-endian |
| 0x0c | 4 | height, little-endian |
| 0x10 | 4 | payload length, little-endian |
| 0x14 | n | payload bytes |

The default seeds are tiny synthetic frames, not captured media. For the
`libnativeImageUtils.so` path, start with `call mode = 1` and switch the
`TARGET_SYMBOL`/adapter once the exact function prototype is confirmed in Ghidra.

## Prerequisites

- Android SDK + NDK installed locally
- `adb`
- `afl-fuzz` from AFL++
- Frida client/server pinned to **16.1.4** for this target
- An Android ARM32 guest or device that can actually run the harness

### Important constraints

- The known-good Frida pairing for this repo's Android 8.1 / ARM32 work is
  **client + server 16.1.4**. Newer Frida releases have been observed to crash
  on this target family during attach/injection.
- AFL++ Frida persistent mode is **not** the first-choice path here; AFL++
  documents persistent mode as x86/x64/aarch64-only, so this scaffold starts
  with in-memory fuzzing and a normal harness entrypoint instead.
- If you use the Android emulator, keep the existing ARM32 caveat in mind:
  the workable setup uses the SDK's ARM qemu binary directly, not the top-level
  `emulator` launcher. Expect **TCG speed**, not KVM speed.
- The harness and workspace are designed to be disposable. All output lands
  under `work/` and stays out of git.

## Quick start

```bash
./bin/setup.sh
./bin/build-harness.sh
./bin/run.sh --dry-run
```

The `--dry-run` output shows the exact commands and paths that will be used.
When the device and Frida server are ready, drop `--dry-run` to start the loop.

## Output layout

Created automatically under `work/`:

- `work/seeds/` — synthetic seed corpus
- `work/build/` — compiled Android ARM32 harness and Frida mode library
- `work/device/` — push-ready device staging area
- `work/out/` — AFL++ output directory
- `work/logs/` — host-side logs from setup/build/run

## Build knobs

The wrapper scripts accept these key environment variables:

| Variable | Purpose |
|---|---|
| `ANDROID_NDK_ROOT` | NDK root used to cross-compile the ARM32 harness |
| `AFLPP_ROOT` | Local AFL++ checkout used to build `frida_mode` |
| `FRIDA_VERSION_PIN` | Defaults to `16.1.4`; the run script refuses mismatches |
| `TARGET_SO_PATH` | Path to the target shared library on the host |
| `TARGET_SYMBOL` | Native entrypoint or adapter symbol to call from the harness |
| `TARGET_CALL_MODE` | `raw_buffer` or `image_frame` |
| `REMOTE_DIR` | Device staging path, default `/data/local/tmp/flock-afl-frida` |

## Related docs

- `tools/README.md`
- `tools/jni-harness/README.md`
- `docs/wiki/alpr-pipeline.md`
