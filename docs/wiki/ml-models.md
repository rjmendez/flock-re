# ML models

The neural networks are shipped as files inside the firmware, so the device's detection
capability is inspectable.

- **Format:** TensorFlow Lite (`.tflite`, FlatBuffer), under `assets/flock_models/` in the
  [detection app](apps.md).
- **Examples in this dump:** a large fp16 detector (~92 MB) plus smaller "nano/pico" variants
  (SSD `flock_small` 300×300, YOLOv5 family).
- **Key class:** the detectors expose a `licensePlate` output class used by the
  [ALPR pipeline](alpr-pipeline.md).
- **OCR is not a model file** — character reading uses the FastCV MSER/NN8 routine in native
  code, not a TFLite model.

Inspecting a `.tflite` (inputs/outputs/labels/ops) needs a FlatBuffer/TFLite parser.

## See also
- [ALPR pipeline](alpr-pipeline.md) · [Apps](apps.md)
