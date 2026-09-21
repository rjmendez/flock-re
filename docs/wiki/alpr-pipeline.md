# ALPR pipeline

Plate **detection and localization** happen on the device; the final plate-number **read (OCR)
is server-side** — see stage 4.

Stages:
1. **Capture** — camera streams YUV frames.
2. **Convert** — `libnativeImageUtils.so` does YUV↔RGB conversion and scaling.
3. **Detect** — TFLite object detectors (SSD + YOLOv5, CPU float32, optional GPU delegate) locate
   a `licensePlate` bounding box. See [ML models](ml-models.md).
4. **Read (OCR) — server-side.** The device does plate **localization + quality scoring** in native
   code (Qualcomm FastCV **MSER** region proposal / `fcvMser*`, `MSER_NN8_*`), but produces **no
   plate-text string**: `libnativeML.so` exposes no text-returning JNI method (no `nativeGetPlateText`)
   and the upload schema has **no plate-text field** (`Detection` carries only class/confidence/
   quality/bbox/direction/trackId — see [Backend protocol](backend-protocol.md)). The character
   read (image→text) runs in the cloud on the uploaded crop. *(Correction to an earlier note that
   read the FastCV MSER/NN8 native code as on-device OCR; the code does region/quality work, not the
   stored/transmitted text.)*
5. **Track & score** — a multi-frame tracker plus quality/exposure scoring keeps the best crop and
   emits one "asset" (a confident detection), stored in the `sessions`/`assets` tables
   ([Data & storage](data-and-storage.md)).

Core native libs: `libnativeML.so` (JNI `NativeML`) and `libnativeImageUtils.so`, both 32-bit ARM.

## Memory-safety defects (found statically)
- **Integer overflow → out-of-bounds** in the shared YUV size-validation check in
  `libnativeImageUtils.so`: a 32-bit `width*height*3/2` multiply can wrap, defeating the bounds
  check on attacker-influenced frame dimensions. See [Security posture](security-posture.md).
- **Process-kill DoS:** the FastCV MSER localization initializer calls `exit(1)` on out-of-range
  derived parameters, terminating the whole host process.

## Reproducibility (dynamic analysis is feasible)
The inference path is runnable off-device: `libnativeML.so` (32-bit ARM) plus the shipped
`.tflite` detectors load in a stock **Android 8.1 emulator**, and there is **no cert pinning** on
the upload path — so a JNI harness can drive the on-device localization and observe exactly what
the crop→cloud step sends, without touching any live service. A static reproduction (running the
detectors on synthetic inputs) is already in `tools/modeltest/detect.py`; the live-JNI harness is
future work, listed here so the claim is checkable rather than asserted.

For the first native-only fuzzing pass, see `tools/jni-harness/afl-frida/`: it keeps the input
shape explicit and starts from `libnativeImageUtils.so`-style non-JNI code before layering on the
JNI path.

## Runtime behavior (confirmed from crash-pack logs)
- The live on-device detector is a **single native YOLO** (`yolo_pico3_float16` via `nativeML`),
  constant across 6 months, running **CPU-only** (no GPU/NNAPI/DSP delegate in logs).
- Per-detection **confidence scores are never logged**; gating uses proxies (plate pixel-width,
  a day/night threshold split).
- **No hotlist/watchlist matching happens on-device** — Flock's headline "wanted plate" feature
  is entirely backend-side; the camera just uploads captures + metadata.
- **No per-detection GPS** on-device. What leaves per session is an MP4 (plate + vehicle brackets)
  plus session/asset metadata.
- The encoder applies an ROI privacy **blur to ~47%** of videos and dehaze to ~19%; retention is
  a disk-85%-full + age policy.

## See also
- [ML models](ml-models.md) · [Apps](apps.md) · [Security posture](security-posture.md) · [Backend protocol](backend-protocol.md) · [Crash logs](crash-logs.md)
