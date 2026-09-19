# ML models

The detectors are shipped as files in the firmware, so the camera's detection capability is
inspectable. The plate-number **OCR is not on the device at all** — it runs server-side on the
uploaded crop (see [ALPR pipeline](alpr-pipeline.md)); on-device native code does localization and
quality scoring only.

## What ships
- **5 detector `.tflite` files** (SSD + YOLOv5 families) under `assets/flock_models/` (7 counting
  the two legacy models noted below), plus a
  `models.json` manifest and `anchors.json` (1917 SSD anchors). Binary tensor shapes were
  confirmed against the manifest.
- **`licensePlate` class** appears in at least 3 of the 7 detector/label-map configs, with a far stricter tracking
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

## Declared classes (from the model label maps)
- **Live YOLO** (`label_map_all_vehicle.json`): `bicycle`, `licensePlate`, **`person`**, `vehicle`.
- **SSD** (`label_map.json`, 10 classes): `bicycle, bus, car, cat, dog, licensePlate, motorcycle, person, truck, trailer` — note the **person** class.
- Per-class gates are asymmetric: `licensePlate` **minQuality 0.98** (only near-perfect reads kept)
  vs `person` **minQuality 0.01** (kept even at low quality). The large model deliberately omits
  the licensePlate class (`vehicle_no_lp` config) — a cascade design.

## Empirical test (running the model, not the data)
The `pico3` detector was run on public/synthetic inputs (never captures): a street photo →
**person ×30 (0.74) + vehicle ×6 (0.65)**; a two-person photo → **person ×10 (0.55)**; noise/solid
→ **0** (clean baseline). This independently confirms active person detection. Harness:
`tools/modeltest/detect.py`.

Separately, a dynamic-analysis harness ran the same class of extracted `.tflite` model inside a
genuinely-ARM-emulated Android guest — not just a standalone Python/`tflite_runtime` script:
`MLM-2854-pico3-best-fp16.tflite` reproducibly detected 6 `vehicle` boxes at confidence 0.348 on a
synthetic gradient image. This corroborates the "real, working detector" claim with a second,
independent verification method closer to the camera's real execution environment — a live ART
process invoking the model through the app's own code path — rather than only a bare Python
harness. This harness's network egress was verified live-blocked throughout
(`iptables -P OUTPUT DROP`), and, as above, no captured/real device data was used; the input was
procedurally generated. Cite: `deep/swarm/jni-harness/FINDINGS.md`. Reproduce:
`tools/jni-harness/README.md`.

## See also
- [ALPR pipeline](alpr-pipeline.md) · [Apps](apps.md) · [Claims vs evidence](claims-vs-evidence.md)
