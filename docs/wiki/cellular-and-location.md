# Cellular & location

A self-contained cellular edge device. Notably it carries **two distinct radio stacks**.

## Radios
- **SoC-integrated baseband:** Qualcomm MPSS in the `modem` partition, version
  `MPSS.TA.2.3.c1-…-8953_*`, built 2019-04-01. Also hosts GNSS/IZat. Modem state in
  `modemst1/2`, `fsg`, `fsc`.
- **Separate WWAN module:** a physically distinct **Sierra Wireless SWI9X07H** module
  (own baseband, `SierraFwDl` firmware-download tool present) — a second radio subsystem.
- **Baseband exposure:** the MPSS version predates the fix for a published **LTE NAS
  integrity-bypass CVE** (rogue-base-station class, CVSS 9.8). Plausibility by version/date,
  *static-only*. See [Security posture](security-posture.md).

## SIM / carrier
- **eSIM (GSMA RSP)** with a baked-in **Twilio bootstrap/fallback profile** auto-activated
  fleet-wide by a connectivity watchdog (`lte_check`).
- On this unit `mcfg` (carrier config) and `fsg` (normally IMEI/MEID/NV) are **byte-for-byte
  zero** — no carrier profile or device-unique identifier recoverable at rest.

## Location
- On-board **GNSS** via Qualcomm's IZat/`gpsdiag` module (DIAG-controlled, XTRA assist, NMEA to
  Android), so detections are geotagged.
- `/dev/diag` is **not** world-accessible (mode 0660, group `oem_*`) and DIAG isn't in the
  default USB gadget config — the DIAG attack surface is not exposed by default.

## See also
- [Hardware](hardware.md) · [Partition map](partition-map.md) · [Security posture](security-posture.md)
