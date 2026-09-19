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
