# Apps

Four cooperating vendor apps (package names generalized). Each has a single job.

| Role | Package (form) | Job |
|---|---|---|
| Detection | `<vendor>.android.objects` | On-device [ALPR pipeline](alpr-pipeline.md); label "DetectionProcessing" |
| Control plane | `<vendor>.android.phonehomeservice` | Device registration, check-in, config |
| Upload | `<vendor>.android.uploadclient` | Sends captured detections/media to backend |
| Updater | `<vendor>.android.<updater>` | Over-the-air firmware/app updates |

- Detection app version in this dump: 6.35.x, signed v1+v2.
- Native code is 32-bit ARM (`armeabi-v7a`); see [ALPR pipeline](alpr-pipeline.md) for the
  detection/OCR libraries.
- Network behavior of the control/upload/updater apps is in [Backend protocol](backend-protocol.md).

## See also
- [ALPR pipeline](alpr-pipeline.md) · [Backend protocol](backend-protocol.md) · [Android userland](android-userland.md)
