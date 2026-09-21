# JNI / ML dynamic-analysis harness

Runs the extracted Flock Falcon native ML library / TFLite models in an **emulated, offline
environment** to observe real behavior — never against a real device or a real Flock backend.
Every input is synthetic (procedurally generated or hand-drawn primitives); no captured
plate/photo/PII from the dump is ever used. Reproduction details are documented in this
directory and in `tools/README.md`.

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

## Component B — AVD/ART path — real app execution achieved (validated setup)

**Validated status: real, unmodified `flock-object` app code runs on genuinely-ARM
hardware-emulated Android, with a real, verified Frida hook.** It is not yet reaching
`NativeML` — it stops on an enumerable set of Android-O+-only framework API calls this
older OS doesn't have — but every previous "fundamental" blocker below was individually
solved. Read bottom-up if you want the history; the short version, if you just want to
reproduce it, is in "Reproducing the validated environment" below.

Earlier attempts (superseded, kept for the record): `armeabi-v7a`-only native libs made the
standard x86/x86_64/arm64-v8a emulator images unusable (no ARM translation, no 32-bit
personality — `INSTALL_FAILED_NO_MATCHING_ABIS`); a genuine `armeabi-v7a` image was found
(`system-images;android-25;google_apis;armeabi-v7a`, via `sdkmanager --list
--include_obsolete`) but the top-level `emulator` launcher refuses to boot an `'arm'` CPU
architecture at all (`FATAL | CPU Architecture 'arm' is not supported by the QEMU2
emulator`). **Correction for anyone reusing this writeup**: a sibling effort
(`tools/sandbox/`, PR #8) framed the AVD path as blocked by "no `/dev/kvm`" (acceleration) —
that was already wrong (TCG boots fine, just slowly), and turned out to be the wrong layer
entirely once the validated setup found the real fix below.

### Validated setup: the actual fix
The architecture gate above lives **only** in the top-level `emulator` launcher — the
arch-specific `qemu-system-armel(-headless)` binary it normally delegates to (already
shipped inside the same emulator package) has no such check and boots ARM guests fine when
invoked directly:
```bash
export LD_LIBRARY_PATH=$SDK/emulator/lib64:$SDK/emulator/lib64/qt/lib
$SDK/emulator/qemu/linux-x86_64/qemu-system-armel-headless \
  -avd <name> -no-window -no-audio -no-boot-anim -gpu swiftshader_indirect
```
(needed one missing host lib, `libpulse0` — `apt-get install libpulse0`). Boots to a real,
`adb`-connected `ro.product.cpu.abi=armeabi-v7a` guest — genuine ARM CPU emulation, not
x86-with-translation.

From there, three more layers, each with a standard, documented fix:
1. **Install-time SDK gate** (`INSTALL_FAILED_OLDER_SDK`) — needs `minSdkVersion` lowered,
   see manifest-patch tooling below, but a byte patch alone isn't enough (see #2).
2. **`sharedUserId="android.uid.system"` signature mismatch** — the app must be signed with
   the same certificate this AOSP image's core system packages use. Fetch AOSP's own public
   *platform* test key (not a secret — the standard key every generic/engineering AOSP build
   ships with) and re-sign with that instead of a fresh debug key:
   ```bash
   curl -sL -o platform.pk8 'https://android.googlesource.com/platform/build/+/master/target/product/security/platform.pk8?format=TEXT'
   curl -sL -o platform.x509.pem 'https://android.googlesource.com/platform/build/+/master/target/product/security/platform.x509.pem?format=TEXT'
   base64 -d platform.pk8 > platform.pk8.dec && base64 -d platform.x509.pem > platform.x509.pem.dec
   openssl pkcs8 -inform DER -nocrypt -in platform.pk8.dec -out platform.key.pem
   openssl pkcs12 -export -in platform.x509.pem.dec -inkey platform.key.pem -out platform.p12 -name platformkey -passout pass:<pw>
   apksigner sign --ks platform.p12 --ks-pass pass:<pw> --ks-key-alias platformkey --out signed.apk unsigned.apk
   ```
3. **DEX format version** (`Unrecognized version number ... 038`) — the compiled dex uses a
   format version this API 25 ART doesn't parse at all. A manifest-only byte patch can't fix
   this; it needs the full `apktool d` → edit → `apktool b` round-trip, which re-desugars the
   bytecode to a compatible version (`037`) as a side effect of targeting a lower
   `minSdkVersion`. That round-trip previously failed on this APK's adaptive-icon resources
   (`<adaptive-icon> elements require a sdk version of at least 26`) — fixed by simply
   **deleting** `res/mipmap-anydpi/{ic_launcher,ic_launcher_round}.xml` (the app already ships
   full legacy PNG icons at every density; the adaptive-icon XMLs are a purely cosmetic
   API-26+ enhancement on top, safe to drop). The rebuild also needs `zipalign -p 4` before
   signing (apktool doesn't guarantee native-lib page alignment on rebuild) or install fails
   with `INSTALL_FAILED_INVALID_APK: Failed to extract native libraries, res=-2`.

**Real, OS-enforced network isolation** (not just app-level hook discipline) is applied
before running any of this: `adb root` + on-device `iptables -P OUTPUT DROP` with a
loopback-only exception, verified live (a real `ping` returns `Operation not permitted`).
This matters because nothing about the host WSL/emulator stack blocks real outbound network
access by default — confirmed by legitimate outbound calls during environment setup (Google's
sdkmanager repo, Ubuntu's apt mirrors, `android.googlesource.com`).

With all three layers fixed, the real, only-cosmetically-modified app installs and runs:
`FlockApplication.onCreate()` → `CameraSettings.getCoreValues()` → real Kotlin code
executing on real ARM hardware emulation, further than this project has ever observed this
app run. It stops on `NoSuchMethodError` for `ContentResolver`'s 4-arg
`(Uri, String[], Bundle, CancellationSignal)` `query()` overload — added in API 26, absent
from this OS, called from at least 3 sites in the app (`CameraSettings.kt:319`, `:569`,
`ApnHelper.kt:317`; everywhere else already uses the always-valid 5-arg legacy form).

### `frida/coreValues_hook.js` - Iteration 6 caller-level wrapper hooks
The narrow Iteration 6 loop keeps the workaround at app-level wrappers rather than patching absent
framework APIs. The active bypass stack now includes:
- `CameraSettings.getSettingsFromContentProvider(Context)` / legacy `getCoreValues*` wrappers to bypass API-26 `ContentResolver.query(..., Bundle, CancellationSignal)` call sites.
- `FlockBootstrapperActivity.onStart()` API<26 compatibility path that replaces `startForegroundService(...)` with `startService(...)`.
- `FlockForegroundService.onCreate()` / `onStartCommand(...)` compatibility hooks to skip API-26 notification/bootstrap paths on API 25.

Run it against the known-good Frida pairing for this target (client/server `16.1.4`):
```bash
frida -U -f com.flocksafety.android.objects -l tools/jni-harness/frida/coreValues_hook.js
```
Expected signal:
```
[HOOK] CameraSettings wrapper hook active for: ...
[HOOK] getSettingsFromContentProvider(android.content.Context) called - narrow Iteration 6 caller-side bypass before API26+ ContentResolver.query(Uri,String[],Bundle,CancellationSignal).
[HOOK] FlockBootstrapperActivity.onStart compatibility hook active - replacing API26 startForegroundService() with startService().
[HOOK] FlockForegroundService.onStartCommand(...) bypassed before scheduled-thread startup on API<26.
```
This keeps the workaround narrow and reproducible: app-level caller wrappers and targeted
runtime compatibility hooks only, no synthetic data, and no framework method monkeypatching.

**Frida version note**: current Frida (17.18.0) SIGSEGVs its own injected agent on attach to
this API 25/Nougat ART process (confirmed via `adb logcat` tombstone). An older release,
`16.1.4` (matched client+server), attaches and injects cleanly. Use 16.1.4 specifically for
injection against this target; the newer CLI is fine for everything else (`frida-ps`, etc.).

`frida/hooks.js` (the original, still-unexecuted skeleton for the crop→cloud/phone-home
interception) remains prepared for once execution reaches that far.

Full narrative, every log, and the "if picking this back up" next steps:
dump's `FINDINGS.md`, in the section covering the validated setup.

### Component C — AFL++ / Frida scaffold for the ARM32 native layer

The new `afl-frida/` subtree is the lower-friction starting point for coverage-guided fuzzing of
the ARM32 native path, beginning with `libnativeImageUtils.so`-style code that does not require a
JNI bridge first.

```bash
cd tools/jni-harness/afl-frida
./bin/setup.sh
export ANDROID_NDK_ROOT=/path/to/android-ndk
export AFLPP_ROOT=/path/to/AFLplusplus
export TARGET_SO_PATH=/path/to/extracted/libnativeImageUtils.so
export TARGET_SYMBOL=<real_native_symbol>
export TARGET_CALL_MODE=image_frame
./bin/build-harness.sh
./bin/run.sh --dry-run
```

Input contract and outputs are documented in `afl-frida/README.md`. The run wrapper enforces the
known-good Frida pin (`16.1.4`) and refuses to continue if the host/device pairing does not match.
If you point this at the emulator, keep the ARM32/TCG caveat in mind: it works, but it is slow.

## Manifest patch tooling (`manifest-patch/`)

Small, reusable scripts used to make the one narrowly-authorized deviation documented in
`FINDINGS.md` (earlier attempts): lowering `flock-object.apk`'s `minSdkVersion` from 27 to 25 to get
past an installer SDK-version gate, and nothing else.

- `extract_manifest.py` — pulls the raw compiled `AndroidManifest.xml` bytes out of an APK's
  zip, unmodified.
- `patch_min_sdk.py` — parses the real Android binary-XML (AXML) chunk structure
  (`ResChunk_header` / `ResXMLTree_node` / `ResXMLTree_attrExt` / `ResXMLTree_attribute`) to
  find the `<uses-sdk android:minSdkVersion>` attribute's raw 4-byte integer value and
  overwrites *only* those 4 bytes, asserting the expected old value first. **Validated setup update**:
  this alone is enough to pass the install-time SDK gate, but not enough to actually run on
  this specific APK — the compiled dex uses a bytecode format version this old ART doesn't
  parse at all, which only the full `apktool d`/edit/`apktool b` round-trip fixes (it
  re-desugars the bytecode as a side effect). That round-trip does hit `aapt2 link` failing on
  this APK's adaptive-icon resources (`<adaptive-icon> elements require a sdk version of at
  least 26`) — resolved by deleting `res/mipmap-anydpi/{ic_launcher,ic_launcher_round}.xml`
  (the app already ships full legacy PNG icons at every density as a fallback; a
  resource-only, zero-logic change). See the validated-setup section in `FINDINGS.md` for the full recipe
  including the required `zipalign -p 4` pass. Keep this byte-patch script around regardless
  — it's the right tool for APKs that don't also need dex desugaring.
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
