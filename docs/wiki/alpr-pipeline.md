# ALPR pipeline

Plate detection and reading happen **on the device**, not in the cloud.

Stages:
1. **Capture** — camera streams YUV frames.
2. **Convert** — `libnativeImageUtils.so` does YUV↔RGB conversion and scaling.
3. **Detect** — TFLite object detectors (SSD + YOLOv5, CPU float32, optional GPU delegate) locate
   a `licensePlate` bounding box. See [ML models](ml-models.md).
4. **Read (OCR)** — on-device text recognition via Qualcomm FastCV **MSER** + an NN8 character
   classifier (`fcvMser*` / `MSER_NN8_*`). **No cloud OCR, and no OCR model file** — it's native code.
5. **Track & score** — a multi-frame tracker plus quality/exposure scoring keeps the best read and
   emits one "asset" (a confident detection), stored in the `sessions`/`assets` tables
   ([Data & storage](data-and-storage.md)).

Core native libs: `libnativeML.so` (JNI `NativeML`) and `libnativeImageUtils.so`, both 32-bit ARM.

## Memory-safety defects (found statically)
- **Integer overflow → out-of-bounds** in the shared YUV size-validation check in
  `libnativeImageUtils.so`: a 32-bit `width*height*3/2` multiply can wrap, defeating the bounds
  check on attacker-influenced frame dimensions. See [Security posture](security-posture.md).
- **Process-kill DoS:** the FastCV MSER OCR initializer calls `exit(1)` on out-of-range derived
  parameters, terminating the whole host process.

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
