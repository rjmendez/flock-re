# Android userland

The device runs stock-derived Android 8.1, heavily customized by the vendor.

- **Version:** Android 8.1.0, API 27, build `OPM1.171019.026`, `release-keys`, `user` build.
- **Build vs patch date:** built 2025-06-05 but security-patch level frozen at **2018-06-05** —
  see [Security posture](security-posture.md).
- **Layout:** `system` (framework + [apps](apps.md)), `vendor` (HALs, native libs, SELinux
  policy), `oem` (vendor customization). 32-bit userland (`armeabi-v7a`).
- **Vendor customization:** custom SELinux domains and init entries (device-specific property
  names and paths under `/data/vendor/<vendor>/` and `/persist/<vendor>/`), a modem-restart
  hook, and an eSIM identifier read path.
- **Carrier leftovers:** stock reference-BSP carrier variant strings remain in `vendor` build
  props (inherited from the SoM vendor image, not device-specific).

## See also
- [Apps](apps.md) · [ALPR pipeline](alpr-pipeline.md) · [Partition map](partition-map.md)
