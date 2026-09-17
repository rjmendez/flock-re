# Prior work & what's new

Public coverage of this leak is extensive but converges on hardware, boot/root, and the
*scale* of surveillance. This project's deep dive into the encrypted media, the crash-pack
logs, and the runtime protocol is largely new territory.

## What's publicly established
- **404 Media / WIRED** (broke it): the "stegan0gram" collective physically pulled a Falcon
  camera and copied its storage → DDoSecrets (~28.55 GB). ~**1.6M images of ~50,200 vehicles
  over ~21 days**; the software **detects people, not just plates/vehicles** — contradicting
  Flock's public "we don't track people" line.
- **DDoSecrets** hosts the dataset (partition images, APKs, media).
- **Micah Lee** — hardcoded API key in the shared lib; plaintext Auth0 client id/secret in
  `/persist`; named backend hosts; Android 8.1 / 2018 patch; kernel 3.18.71.
- **IPVM** — "Dissecting Flock": unlocked bootloader, unsigned firmware flashable, DEBUG
  kernel, missing APK signature verification (SoC stated as Snapdragon 625).
- **GainSec / Jon Gaines** — the largest vuln effort: ~51–55 findings, ~22 CVEs across the
  product line (unlocked bootloader, disabled secure boot, unauthenticated EDL, hardcoded
  default credential; a Magisk root method). SoM stated as Open-Q 624A / MSM8953.
- **colonelpanichacks/flock-you** — a passive BLE/Wi-Fi Flock-camera detector built from
  firmware signatures. **kernelstub/FlockCamRE** — hardware teardown docs (repo since removed;
  author's account reportedly banned).

## What appears NOT publicly covered (this project's contribution)
- **Crash-pack log contents.** The mechanism is public (CVE-2025-59403), but no source walks
  an actual pack's per-app logs. The app-log set here (`objects`, `cachaca`, `encoding`,
  `uploadclient`, `phonehomeservice`, `bigboibud`, `medallalight`, `qualitycontrol`, …) does
  not appear by name in any public writeup. See [Crash logs](crash-logs.md).
- **A static upload auth token leaked in cleartext logs** (~3,906×, 6+ months) — unreported.
- **Decoded runtime protocol** — the exact endpoint set, phone-home cadence, telemetry payload
  size, and the ~1,950-pod backend fleet. See [Backend protocol](backend-protocol.md).
- **Media crypto, precisely** — dm-crypt `aes-128-cbc-essiv` with a colocated plaintext key,
  decryption *verified* (public framing is a loose "unencrypted key"). See [Data & storage](data-and-storage.md).
- **modem/cellular diagnostics** — `modemInfo.txt` LTE state; no public teardown exists.
- **On-device data model** — that hotlist/watchlist matching is **not** on-device, per-detection
  has no GPS, and ~47% of videos are ROI-blurred (from live logs). See [ALPR pipeline](alpr-pipeline.md).
- **Unresolved SoC discrepancy** — IPVM ("SD625") vs GainSec/flock-you ("MSM8953"); nobody has
  publicly reconciled it (they're the same MSM8953 die; "Snapdragon 625" is its market name).

## See also
- [Crash logs](crash-logs.md) · [Backend protocol](backend-protocol.md) · [Security posture](security-posture.md) · [Home](Home.md)
