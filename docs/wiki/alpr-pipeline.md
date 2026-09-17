# ALPR pipeline

Plate detection and reading happen **on the device**, not in the cloud.

Stages:
1. **Capture** — camera streams YUV frames.
2. **Convert** — `libnativeImageUtils.so` does YUV↔RGB conversion.
3. **Detect** — TFLite object detectors (SSD + YOLOv5 variants, CPU float32, optional GPU
   delegate) locate a dedicated `licensePlate` class bounding box. See [ML models](ml-models.md).
4. **Read (OCR)** — on-device text recognition via Qualcomm FastCV **MSER** + an NN8 character
   classifier (`fcvMser*` / `MSER_NN8_*`). No cloud OCR.
5. **Track & score** — a multi-frame tracker (Hybrid/MinAssets modes) plus quality/exposure
   scoring keeps the best read and emits one "asset" (a confident detection).

Core native lib: `libnativeML.so` (JNI class `<vendor>.android.nativeml.NativeML`), 32-bit ARM.
Ghidra entrypoints of interest: `nativeInit/Start/AddAsset/ProcessSession`, `processStreamReport`,
`loadAnchors`.

## See also
- [ML models](ml-models.md) · [Apps](apps.md) · [Backend protocol](backend-protocol.md)
