# Partition map

54 partitions, legacy non-A/B Qualcomm layout (`*bak` = backup copies, not live A/B slots).
Note: the `systembk`/`vendorbk` backups here hold a **~26-month-older bootable firmware** that a
downgrade can install cleanly — see [OTA & updates](ota-updates.md). Grouped by role; sizes from
this dump.

## Qualcomm boot & trust — see [Boot chain](boot-chain.md)
| Partition | Purpose |
|---|---|
| `sbl1` (+bak) | Secondary bootloader |
| `rpm` (+bak) | Resource/power management firmware |
| `tz` (+bak) | TrustZone / secure world (QSEE) |
| `devcfg` (+bak) | Device config for TrustZone |
| `aboot` (+bak) | Applications bootloader (LK) |
| `cmnlib`,`cmnlib64`,`keymaster`,`lksecapp` (+bak) | Secure-world libraries & trustlets |
| `keystore` | Hardware-backed key storage |
| `devinfo` | Bootloader/verified-boot state (unlock flag) |

## Android userland — see [Android userland](android-userland.md)
| Partition | Size | Purpose |
|---|---|---|
| `boot` (+`bootbk`) | 32 MiB | Kernel + ramdisk |
| `recovery` | 32 MiB | Recovery kernel/ramdisk |
| `system` (+`systembk`) | 1.5 GiB | Android framework + [apps](apps.md) |
| `vendor` (+`vendorbk`) | 384 MiB | HALs, native libs, SELinux policy |
| `oem` | 256 MiB | OEM/Flock customization |
| `cache` | 64 MiB | Update/scratch cache |

## Cellular / radio — see [Cellular & location](cellular-and-location.md)
| Partition | Purpose |
|---|---|
| `modem` | Baseband (NON-HLOS) firmware |
| `modemst1`/`modemst2`, `fsg`, `fsc` | Modem filesystem/state |
| `mcfg` | Carrier/APN config |
| `dsp` | ADSP firmware |

## Data & device — see [Data & storage](data-and-storage.md)
| Partition | Size | Purpose |
|---|---|---|
| `media` | 18 GiB | Captured images/video store |
| `userdata` | 6.1 GiB | App data, databases, config, cached tokens |
| `persist` | 32 MiB | Device identity/settings; survives factory reset |
| `misc`,`config`,`mota` | — | Boot/update flags |
| `logdump` | 64 MiB | Crash/log ring buffer |
| `splash` | 11 MiB | Boot splash image |

Other Qualcomm housekeeping partitions (`mdtp`, `apdp`, `msadp`, `dip`, `sec`, `limits`,
`syscfg`, `dpo`, `ssd`, `DDR`) are small and platform-standard.

## See also
- [Boot chain](boot-chain.md) · [Data & storage](data-and-storage.md) · [Glossary](glossary.md)
