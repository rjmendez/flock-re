# Tier-2 Environment Unblock Runbook
**Generated**: 2026-09-19  
**Scope**: AFL++/Frida fuzzing on this host  
**Status**: All critical components available; PATH setup required

## Executive Summary

All required components for AFL++/Frida fuzzing are **installed and functional** on this host:
- ✓ Android NDK (two versions available)
- ✓ AFL++ 5.03c (Frida-mode capable)
- ✓ Frida client 16.1.4 + CLI tools
- ✓ Build tools (cc, make, ndk-build, adb)

**Single blocker**: Environment variables not set in shell. This runbook provides copy-paste commands to unblock.

## Component Status

| Component | Status | Location | Version |
|-----------|--------|----------|---------|
| Android NDK 27.2 | ✓ Ready | `~/Android/Sdk/ndk/27.2.12479018` | 27.2.12479018 |
| Android NDK 26.3 | ✓ Ready | `~/Android/Sdk/ndk/26.3.11579264` | 26.3.11579264 |
| AFL++ binary | ✓ Ready | `~/.local/bin/afl-fuzz` | 5.03c |
| Frida Python client | ✓ Ready | `python3 -m frida` | 16.1.4 |
| Frida CLI tools | ✓ Ready | `~/.local/bin/frida*` | 12.1.3 (tools) |
| C Compiler | ✓ Ready | `/usr/bin/cc` | GCC |
| Build tool: make | ✓ Ready | `/usr/bin/make` | - |
| Android ADB | ✓ Ready | `/usr/bin/adb` | 1.0.41 |

**Note**: frida-server is **not** in PATH but can be pulled from Frida's GitHub releases or downloaded via `frida-ls-devices` if needed for remote injection. For local Frida harness work, the client library is sufficient.

## Quick Unblock

### 1. **For bash/sh shells (one-time per terminal session)**

```bash
export ANDROID_NDK_ROOT=~/Android/Sdk/ndk/27.2.12479018
export PATH="~/.local/bin:$PATH"
export AFLPP_ROOT=/path/to/aflpp  # if using a custom AFL++ checkout
```

### 2. **For persistent .bashrc/.bash_profile setup**

Add to `~/.bashrc`:

```bash
# AFL++ / Frida Tier-2 Environment
export ANDROID_NDK_ROOT="${HOME}/Android/Sdk/ndk/27.2.12479018"
export PATH="${HOME}/.local/bin:${PATH}"
# export AFLPP_ROOT="${HOME}/aflpp"  # uncomment if you have a custom AFL++ checkout
```

Then reload:
```bash
source ~/.bashrc
```

### 3. **Using the setup script (if you have shell wrapper in place)**

```bash
cd ~/development/flock-re/tools/jni-harness/afl-frida
./bin/setup.sh
```

## Verification Checklist

After applying environment setup, verify in a new terminal:

```bash
# Should all return 0 exit code
[ -n "$ANDROID_NDK_ROOT" ] && [ -d "$ANDROID_NDK_ROOT" ] && echo "✓ NDK Root set"
command -v afl-fuzz && echo "✓ afl-fuzz in PATH"
python3 -c "import frida; print('✓ frida available')"
[ -x ~/.local/bin/frida ] && echo "✓ frida-tools available"
[ -x "$(command -v ndk-build)" ] && echo "✓ ndk-build in PATH"
```

## If Using NDK 26.3 Instead

If you prefer the older NDK version for compatibility:

```bash
export ANDROID_NDK_ROOT="${HOME}/Android/Sdk/ndk/26.3.11579264"
```

Both versions are installed and functional.

## Common Issues & Solutions

### Issue: `afl-fuzz: command not found`
**Cause**: `~/.local/bin` not in PATH  
**Fix**: Add `export PATH="$HOME/.local/bin:$PATH"` to your shell profile

### Issue: `ndk-build: command not found`
**Cause**: `$ANDROID_NDK_ROOT` not set or incorrect  
**Fix**: Verify with `echo $ANDROID_NDK_ROOT` and ensure it points to a valid NDK directory

### Issue: Frida attach fails with "version mismatch"
**Cause**: Host frida-tools (16.1.4) doesn't match device/server version  
**Fix**: Device frida-server should be 16.1.4; download from [Frida releases](https://github.com/frida/frida/releases/tag/16.1.4)

### Issue: `libnativeImageUtils.so` not found during linking
**Cause**: Target `.so` path in harness is hardcoded; project needs to configure `TARGET_SO_PATH`  
**Fix**: Check `README.md` for environment variable setup before running `./bin/build-harness.sh`

## Next Steps

1. **Apply environment setup** using one of the methods above
2. **Verify** with the checklist
3. **Build and test** the harness:
   ```bash
   cd ~/development/flock-re/tools/jni-harness/afl-frida
   ./bin/setup.sh
   ./bin/build-harness.sh
   ./bin/run.sh --dry-run
   ```
4. **Review output** from `--dry-run` before running full fuzzing

## Environment Variables Reference

| Variable | Default | Purpose | Example |
|----------|---------|---------|---------|
| `ANDROID_NDK_ROOT` | Not set | Root of Android NDK | `~/Android/Sdk/ndk/27.2.12479018` |
| `PATH` | System default | Executable lookup path | Must include `~/.local/bin` |
| `AFLPP_ROOT` | Optional | Custom AFL++ checkout | `~/aflpp` (if not using system) |
| `FRIDA_VERSION_PIN` | `16.1.4` | Frida version constraint | Keep as 16.1.4 for this target |
| `TARGET_SO_PATH` | Not set | Target library path | Set before `build-harness.sh` |
| `TARGET_SYMBOL` | Not set | Entrypoint symbol | Set before `build-harness.sh` |
| `REMOTE_DIR` | `/data/local/tmp/flock-afl-frida` | Device staging dir | Android device path |

## Final Status

✅ **UNBLOCKED**: All components available. Only prerequisite is setting `ANDROID_NDK_ROOT` and ensuring `~/.local/bin` is in `PATH`.

---

**Related Documents**:
- `README.md` — Harness design and prerequisites
- `tools/README.md` — Tool organization  
- `tools/jni-harness/README.md` — JNI harness guide
