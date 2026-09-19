# JNI / ML dynamic-analysis harness

Runs the extracted Flock Falcon native ML library / TFLite models in an **emulated, offline
environment** to observe real behavior — never against a real device or a real Flock backend.
Every input is synthetic (procedurally generated or hand-drawn primitives); no captured
plate/photo/PII from the dump is ever used. Full status, evidence, and the AVD/ABI blocker
write-up live in the dump's evidence tree: `<dump>/deep/swarm/jni-harness/FINDINGS.md`
(not committed here — see `tools/README.md`'s "Reproduce" section for the dump layout).

## Component A — TFLite-only path (working)

- `tflite/gen_synth_inputs.py` — generates 4 synthetic test images (noise, flat gray, gradient,
  a hand-drawn fake-vehicle silhouette) into `synthetic_inputs/` next to this file.
- `tflite/run_tflite_models.py` — loads the real extracted `.tflite` weights from the dump's
  `deep/tflite-models/extracted/assets/flock_models/`, runs real inference against each
  synthetic image, and writes `results/tflite_component_a_results.json`.

```bash
python3 tflite/gen_synth_inputs.py
python3 tflite/run_tflite_models.py   # needs numpy<2, pillow, tflite-runtime — see tools/README.md
```

Confirmed reproducible: `MLM-2854-pico3-best-fp16.tflite` on the synthetic gradient image
consistently detects 6 `vehicle` boxes at confidence 0.348.

## Component B — AVD/ART path (blocked, not run against a live process)

`frida/hooks.js` is a prepared, **unexecuted** hook skeleton for intercepting the crop→cloud
and phone-home handoff once a working runtime exists. It's blocked on a real ABI gap, not a
tuning issue: `flock-object.apk` ships `armeabi-v7a`-only native libraries, and none of the
Android emulator system images currently published by Google (checked: API 24/25/27/28,
x86/x86_64/arm64-v8a) bundle ARM binary translation (`libhoudini`) or a 32-bit personality —
`adb install` fails with `INSTALL_FAILED_NO_MATCHING_ABIS` before the app process ever starts.
See the dump's `FINDINGS.md` for the full evidence trail (boot logs, install-failure log,
logcat capture) and what would unblock it (an older houdini-bundled image, if one still
exists, or a real armeabi-v7a/32-bit-capable device over `adb`).

**Update (Session 3)**: a genuine (untranslated) `armeabi-v7a` system image *does* still
exist — `system-images;android-25;google_apis;armeabi-v7a`, via `sdkmanager --list
--include_obsolete` — so the ABI-translation gap above is no longer the operative blocker for
that specific image. The blocker moved one level down: the current `emulator` build
(37.1.11 — the only revision this SDK's `sdkmanager` repository serves at all, obsolete or
not) refuses to boot an `'arm'` (32-bit) guest CPU architecture under any flag, including
`-engine classic` (`FATAL | CPU Architecture 'arm' is not supported by the QEMU2 emulator, the
classic engine is deprecated!`). **Correction for anyone reusing this writeup**: a sibling
effort (`tools/sandbox/`, PR #8) framed the AVD path as blocked by "no `/dev/kvm`"
(acceleration). That was already wrong (TCG boots x86/x86_64 guests fine here, just slowly),
and is now doubly superseded — the real, current blocker for the armeabi-v7a-specific path is
that the emulator binary itself no longer supports the guest architecture at all, independent
of acceleration or host CPU. See the dump's `FINDINGS.md` "Session 3" section for full logs.

## Manifest patch tooling (`manifest-patch/`)

Small, reusable scripts used to make the one narrowly-authorized deviation documented in
`FINDINGS.md` (Session 3): lowering `flock-object.apk`'s `minSdkVersion` from 27 to 25 to get
past an installer SDK-version gate, and nothing else.

- `extract_manifest.py` — pulls the raw compiled `AndroidManifest.xml` bytes out of an APK's
  zip, unmodified.
- `patch_min_sdk.py` — parses the real Android binary-XML (AXML) chunk structure
  (`ResChunk_header` / `ResXMLTree_node` / `ResXMLTree_attrExt` / `ResXMLTree_attribute`) to
  find the `<uses-sdk android:minSdkVersion>` attribute's raw 4-byte integer value and
  overwrites *only* those 4 bytes, asserting the expected old value first. This is safer than
  a full `apktool d`/edit/`apktool b` round-trip, which for this specific APK fails at
  `aapt2 link` time (its adaptive-icon resources require API 26+, so a relink at
  `minSdkVersion=25` errors out) and would otherwise tempt scope creep into touching resource
  files that weren't part of the authorization.
- `rebuild_apk.py` — copies every other zip entry from the original APK byte-for-byte (same
  compression method) and swaps in only the patched manifest entry, dropping the
  now-invalidated original `META-INF/` signing entries. Sign the result yourself, e.g.:
  ```bash
  keytool -genkeypair -keystore debug.keystore -alias debugkey -keyalg RSA -keysize 2048 \
    -validity 10000 -storepass <pw> -keypass <pw> -dname 'CN=debug'
  <build-tools>/zipalign -p 4 out-unsigned.apk out-aligned.apk
  <build-tools>/apksigner sign --ks debug.keystore --ks-pass pass:<pw> \
    --out out-signed.apk out-aligned.apk
  ```
- `apktool.jar` itself is **not** vendored here (23MB third-party binary) — fetch it directly
  from its GitHub releases if attempting the full-rebuild path for a *different* APK that
  doesn't hit the adaptive-icon issue above:
  `curl -sL -o apktool.jar https://github.com/iBotPeaches/Apktool/releases/download/v2.9.3/apktool_2.9.3.jar`
