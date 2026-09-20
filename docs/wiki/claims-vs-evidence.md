# Flock public claims vs the evidence

What the firmware shows, mapped against Flock Safety's public statements. Honest about what the
evidence does and does not support.

## Current confirmation table

This page summarizes what the current dump supports, does not support, or cannot
resolve from the evidence in this repo. The status below is intentionally
conservative: claims are only marked as supported when the firmware, reproduced
model behavior, or static evidence directly matches them.

| Claim | Current status | Evidence in this repo | Notes |
| --- | --- | --- | --- |
| "We don't track/identify people — only vehicles/plates." | Disproven | The detector label map includes `person`; model tests reproduce `person` detections on ordinary public photos and the local `modeltest` harness documents the behavior. | This contradicts the public claim directly. |
| "Devices are secure / secure boot." | Disproven | Boot-chain and security findings document a test-signed trust chain and an unlocked bootloader. | This is not a theoretical concern; the dump contains the evidence. |
| "Your data is encrypted and secure." | Materially misleading | The capture volume is dm-crypt, but the key is stored beside it in plaintext; a static upload token is logged in cleartext; a fleet-wide API key and unauthenticated servicing path are documented. | The issue is not merely a wording mismatch; the evidence shows significant exposure. |
| "No facial recognition." | Supported (not refuted) | The pipeline contains person object-detection, not a face-recognition model or class. | The claim is supported by absence of the relevant model/class in the dump. |
| "No audio / no microphone." | Over-permissioning, not proof of recording | Three apps declare `RECORD_AUDIO`, but no audio-capture logic is present in the decompiled apps. | This is a privacy red flag, not proof of active audio capture. |
| "Footage auto-deletes after 30 days." | Not verifiable from the dump alone | The repo documents a cloud-retention claim versus a rolling on-device buffer; the dump does not prove the cloud policy or the device-side deletion path. | This is a claim about an external service boundary, not a conclusion from the firmware alone. |
| "Crash-pack logs contain no GPS coordinates." | Unresolved / contradictory evidence | `backend-protocol` and model-path evidence show GPS fields are collected/transmitted, while crash-log line-level `ciroc` coordinate excerpts are not yet published in-repo. | External reporting claims `ciroc` lat/lon in logs; this repo now tracks this as a verification gap, not a settled conclusion. |

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
