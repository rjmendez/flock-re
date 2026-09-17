# Boot chain

Standard Qualcomm MSM8953 secure-boot stages, each loading/verifying the next:

`PBL (ROM)` → `SBL1` → `aboot` (Little Kernel) → [`boot`](partition-map.md) (Linux kernel +
Android ramdisk) → Android init.

- **Secure world** (`tz`, `keymaster`, `cmnlib`, `lksecapp`) loads alongside, providing QSEE
  trustlets and key services.
- **Verified boot:** `devinfo` holds the bootloader-unlock / verified-boot state struct.
- **Integrity note:** public teardowns of this device class report an unlocked bootloader and
  a non-production (test-key) signing posture — see [Security posture](security-posture.md).
  (Confirmation from this dump is tracked by the deep-dive; treat as reported-not-yet-verified
  until then.)

## See also
- [Partition map](partition-map.md) · [Security posture](security-posture.md)
