# Device profile

Established from the partition layout; enriched as extraction completes.

## Platform

- **Class:** Qualcomm Snapdragon Android device (Flock Safety ALPR camera).
- **Evidence:** partition set carries the Qualcomm boot chain (`sbl1`, `rpm`,
  `tz`, `devcfg`, `aboot`/LK, `cmnlib`, `keymaster`, `lksecapp`) alongside a
  standard Android userland (`boot`, `recovery`, `system`, `vendor`, `oem`,
  `cache`, `persist`, `userdata`), plus a cellular stack (`modem`/NON-HLOS,
  `modemst1/2`, `fsg`, `mcfg`) — i.e. an LTE-connected camera.
- SoC / exact model / Android version: pin from `system/build.prop` and
  `devinfo` during extraction.

## Partitions (54 total, ~28.6 GiB)

Full table in the leak's `partitions.csv`. Highlights:

| # | name | size | RE interest |
|---|------|------|-------------|
| 01 | modem | 84 MiB | baseband, carrier/APN config |
| 08/09 | tz / tzbak | 2 MiB | TrustZone / QSEE trustlets |
| 12 | dsp | 16 MiB | ADSP firmware |
| 19/20 | aboot | 1 MiB | LK bootloader, secure-boot posture |
| 21/22 | boot / recovery | 32 MiB | kernel + ramdisk, init, fstab, verity |
| 24/51 | system (+bk) | 1.5 GiB | Android framework + the ALPR app |
| 25/52 | vendor (+bk) | 384 MiB | HALs, native libs |
| 27 | persist | 32 MiB | device certs, serials, wifi, DRM |
| 29 | keystore | 512 KiB | keymaster-backed keys |
| 31 | oem | 256 MiB | OEM/Flock customization |
| 53 | media | 18 GiB | captured imagery (PII — aggregate only) |
| 54 | userdata | 6.1 GiB | app data, DBs, config, shared_prefs |

## Prime RE targets

`system` + `vendor` + `oem` (the ALPR application and its native libs) →
`boot` (kernel/ramdisk/verity) → `persist`/`keystore` (identity, certs) →
`modem`/`tz` (baseband + secure world) → `userdata` (runtime config, DBs).

_TODO: fill SoC model, Android version, kernel version, ALPR package name,
backend endpoints from workflow output._
