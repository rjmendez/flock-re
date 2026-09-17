# Flock public claims vs the evidence

What the firmware shows, mapped against Flock Safety's public statements. Honest about what the
evidence does and does not support.

## Disproven
- **"We don't track/identify people — only vehicles/plates."** The detector has a first-class
  **`person`** class (`label_map_all_vehicle.json`: bicycle, licensePlate, **person**, vehicle;
  the SSD label map adds bus/car/cat/dog/motorcycle/truck). Running the model live on ordinary
  public photos, it detects **person** boxes (×30 @ conf 0.74 on a street scene; ×10 @ 0.55 on a
  two-person image) and vehicles — clean baseline (0 on noise/solid). Flock's own model
  contradicts the claim. See [ALPR pipeline](alpr-pipeline.md), [ML models](ml-models.md).
- **"Devices are secure / secure boot."** Test-signed trust chain + unlocked bootloader.
  See [Boot chain](boot-chain.md).

## Materially misleading
- **"Your data is encrypted and secure."** The capture volume is dm-crypt but the key is stored
  in plaintext beside it (decryption verified); a static upload token logs in cleartext ~3,906×;
  a fleet-wide hardcoded API key; unauthenticated servicing server. See
  [Data & storage](data-and-storage.md), [Crash logs](crash-logs.md), [Local attack surface](local-attack-surface.md).

## Cannot disprove (stated honestly)
- **"No facial recognition."** The pipeline does person *object-detection*; **no face-recognition**
  model or class is present → the claim is **supported**, not refutable.
- **"No audio / no microphone."** Three apps (`collins`, `ciroc`, `cachaca`) declare the
  `RECORD_AUDIO` permission, but **no audio-capture code** exists in the decompiled apps → a
  privacy red flag (over-permissioning), **not** proof of recording.
- **"Footage auto-deletes after 30 days."** That is a *cloud* retention claim; on-device is a
  rolling disk-85%+age buffer — not testable from the device. (Note: an on-device archive DB and
  a OneShot "reprocess" path suggest "deleted" media may be republishable — worth a separate look.)

## Reproduce
Model-test harness: `tools/modeltest/detect.py` (+ a Python-3.11 `tflite_runtime` venv). Runs the
extracted detector on any supplied image — never on captured data.

## See also
- [ALPR pipeline](alpr-pipeline.md) · [ML models](ml-models.md) · [Prior work](prior-work.md) · [Security posture](security-posture.md)
