# Model test harness

Run the extracted Flock detector (`.tflite`, an app asset — not capture data) on your own
synthetic or public images to characterize what it detects, at what confidence, and how the
per-class quality gates behave. **Never run it on captured surveillance frames.**

- `detect.py` — load a detector, run on an image or directory, print detections per class.
- Setup: Python 3.11 venv with `numpy<2`, `pillow`, `tflite-runtime` (no 3.12 wheel exists).
- Models + `label_map_*.json` are extracted from the firmware APK assets (`flock_models/`).

Example (public YOLO demo images make good test inputs):
```
python3.11 -m venv venv && venv/bin/pip install 'numpy<2' pillow tflite-runtime
venv/bin/python detect.py --model MLM-2854-pico3-best-fp16.tflite \
    --labels label_map_all_vehicle.json --input ./imgs --conf 0.35
```
The live `pico3` detector has classes `bicycle, licensePlate, person, vehicle`; on ordinary
street/person photos it fires the `person` and `vehicle` classes (see the wiki `claims-vs-evidence`).
