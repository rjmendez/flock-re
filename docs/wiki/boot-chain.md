# Boot chain

Standard Qualcomm MSM8953 secure-boot stages, each loading/verifying the next:

`PBL (ROM)` → `SBL1` → `aboot` (Little Kernel) → [`boot`](partition-map.md) (Linux kernel +
Android ramdisk) → Android init. Secure world (`tz`, `keymaster`, `cmnlib`, `lksecapp`) loads
alongside, providing QSEE trustlets and key services.

## Trust state (confirmed in this dump)
- **Test-signed chain.** TZ/Keymaster/lksecapp/RPM/aboot validate against a generic Qualcomm
  **SecTools TEST** root/intermediate (`OEM_ID=0000`, DEBUG fuse set) — not a production OEM key.
- **Public testkey in aboot.** `aboot` also trusts the world-public **AOSP `testkey`** to verify
  `boot`/`recovery`; its private half ships in AOSP source, so anyone can sign an image aboot
  accepts.
- **Signing inconsistency.** `aboot`'s own leaf cert is under a *different* test CA than the rest
  of the chain and was re-signed 2025-06-05, while the others date to 2018 (tz, keymaster,
  lksecapp) and 2020 (rpm).
- **Bootloader unlocked.** `devinfo` byte-confirmed `is_unlocked=1`, `bootloader_locked=0`.
- **Verified boot flavor.** Legacy per-partition **dm-verity** (fs_mgr `verify` on system/vendor),
  **not AVB2** — and disableable.
- **Keystore partition** is zero-filled on this unit (no key-blob material at capture time).

Net effect: the hardware root of trust is not enforced — see [Security posture](security-posture.md).

## See also
- [Partition map](partition-map.md) · [Security posture](security-posture.md)
