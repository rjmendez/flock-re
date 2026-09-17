# Apps

Cooperating vendor apps (package names generalized). Detection, control, upload, and update are
split across separate apps, plus supporting services.

| Role | Package (form) | Job |
|---|---|---|
| Detection | `<vendor>.android.objects` | On-device [ALPR pipeline](alpr-pipeline.md); label "DetectionProcessing" |
| Control plane | `<vendor>.android.phonehomeservice` | Registration, check-in, config; owns the device-management API client |
| Upload | `<vendor>.android.uploadclient` | Sends captured detections/media (binary protocol, [see backend](backend-protocol.md)) |
| Updater | `<vendor>.android.cameraupdater` | Over-the-air firmware/app updates |
| Auth | `<vendor>.android.sambuca` | The real OAuth2 implementation (an AIDL "Auth0KeyService") the others call |
| Settings | `<vendor>.settings` app | Local `core_values` DB (stores an auth token in plaintext) |
| System control | `<vendor>.system-control` app | Paired-accessory control; `accessory` DB (plaintext auth) |
| Peripheral | `<vendor>.peripheral` app | Hardware/board abstraction; exports a no-permission service with `reformat/encryptMediaPartition()` |
| Device control | `<vendor>.collins` app | Runs an unauthenticated embedded HTTP control server (reboot/adb/live-view/factory-reset) |
| Capture DB | `<vendor>.amarula` app | Owns the ALPR capture DB; an exported receiver exfils it on a broadcast |
| Factory test | `<vendor>.assembly-validator` | Manufacturing test harness — ships in the **production** image with open exported test services |

- **All 15 Flock apps ship `android:debuggable="true"`** in production; a shared library carries a
  default API key (value redacted). See [Local attack surface](local-attack-surface.md).

- Detection app version in this dump: 6.35.x; native code is 32-bit ARM (`armeabi-v7a`).
- The auth service is [exported without a permission](local-attack-surface.md) — a key finding.
- Network behavior of the control/upload/updater apps: [Backend protocol](backend-protocol.md).

## See also
- [ALPR pipeline](alpr-pipeline.md) · [Backend protocol](backend-protocol.md) · [Local attack surface](local-attack-surface.md) · [Data & storage](data-and-storage.md)
