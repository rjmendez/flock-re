# ML models

The detectors are shipped as files in the firmware, so the camera's detection capability is
inspectable. OCR is **not** a model — it's native code (see [ALPR pipeline](alpr-pipeline.md)).

## What ships
- **6 detector `.tflite` files** (SSD + YOLOv5 families) under `assets/flock_models/`, plus a
  `models.json` manifest and `anchors.json` (1917 SSD anchors). Binary tensor shapes were
  confirmed against the manifest.
- **`licensePlate` class** appears in 3 of 4 wired detector configs, with a far stricter tracking
  gate than other classes (e.g. minQuality 0.98 vs 0.01) — plates must be very clean to register.
- The largest/most-accurate model (~92 MB, 620 ops) has **no** licensePlate class — consistent
  with a **cascade** design (a big general detector locating, smaller ones specializing).
- Two older SSD models (`flock_small`, `flock_large`) sit outside the model dir and are
  unreferenced by the manifest — likely dead code.

## Notes for readers
- **IP/exposure:** models are weight-only **fp16**, converted with stock TensorFlow, using only
  standard TFLite ops (no proprietary layers) — fully recoverable from the leaked app, so the
  detector can be studied or benchmarked offline.
- **Manifest drift:** `models.json` declares a wrong output shape for the large YOLO model
  (a copy-paste bug); harmless unless a consumer trusts the manifest over the binary.

## See also
- [ALPR pipeline](alpr-pipeline.md) · [Apps](apps.md)
