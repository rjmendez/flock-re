# Cellular & location

The camera is a self-contained cellular edge device — no wired network needed.

- **Baseband:** Qualcomm MPSS modem firmware in the `modem` partition (NON-HLOS), version
  `MPSS.TA.2.3.c1-…-8953_*`. Modem state lives in `modemst1/2`, `fsg`, `fsc`.
- **Connectivity:** LTE WAN with an **eSIM** (vendor property reads the eSIM EID); a
  vendor hook can restart the modem.
- **Carrier config:** `mcfg` partition holds carrier/APN profiles.
- **Location:** on-board **GNSS** with a diagnostic interface (`gps/gnss/diag`), so each
  detection can be geotagged.

Attack-surface context (baseband/cellular) is public-CVE informational only; this project does
no radio interaction. See [Security posture](security-posture.md).

## See also
- [Hardware](hardware.md) · [Partition map](partition-map.md)
