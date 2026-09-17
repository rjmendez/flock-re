# Local attack surface

On-device components reachable by other apps/processes or over the servicing Wi-Fi AP. Static
findings from decompiled code (file:line grounded); no exploitation performed. Credential values
redacted.

## The `collins` servicing server (critical)
An embedded HTTP server (`WebServer`/NanoHTTPD) on **port 8080**, running as **`system` UID**,
with **no authentication on any route**.
- **How it's reached:** a Wi-Fi AP that the device raises in **installer mode**. SSID =
  `Flock-<last 6 of MAC>`; WPA2 key is a **hardcoded dictionary word (redacted)**. The AP is
  turned on by an internal `WIFI_AP_ON` broadcast (installer mode / `ENTER_INSTALLER_MODE`,
  `NEW_PACKAGE_INSTALLED`, `BOOT_COMPLETED`) and **auto-stops after ~60 s / 20 min** unless a
  client stays connected or the backend-pushable `leaveWifiEnabled` setting keeps it up.
- **21 unauthenticated endpoints**, including:
  - `PUT /api/v1/system/adb/enable` → turns on ADB-over-Wi-Fi = **remote code execution** as system
  - `GET .../crashpack?includeDatabase=true` → **exfil of the ALPR SQLite DBs** (images + GPS)
  - `GET /api/v1/system/modem` → **IMEI / MEID / ICCID / IMSI**
  - `GET /api/v1/system/logs` (unvalidated `packageName`) → logs containing credentials
  - live-view (MJPEG/RTSP), **reboot**, **power-relay** switch (attacker-set duration),
    **battery-deactivate**, **camera-settings tamper**
- No rate-limiting. `debuggable=true`. (Parts map to CVE-2025-59403/59405; the full route set +
  the AP key are not in public writeups.)

## Exported inter-app components
- **`ciroc`** — a **zero-permission exported AIDL** camera service: a `directoryPath` parameter
  enables path traversal to `/persist`, plus a TestCamera frame-injection path.
- **`amarula`** — an **exported, unprotected `DatabaseExportReceiver`**: a broadcast copies the
  full ALPR capture DB to a world-readable path. Its content providers are `normal`-protection.
- **`sambuca` `Auth0KeyService`** — exported, enabling inter-app **live token theft**.
- **`motion`/`sensor`** — an exported `SensorContentProvider` with full CRUD/row-delete; the
  motion app also declares `ACCESS_FINE_LOCATION`.
- **`OneShotReceiver`** — unauthenticated broadcast that overwrites the device's stored identity.

## Root / watchdog
- **`reaperd`** (FlockReaperDaemon) runs as **root** with a **world-writable (0666) command
  socket** — a local privilege-escalation foothold; governed by the undocumented
  `flock_starsan_prop` SELinux type.

## Remote debug
- **ADB-over-Wi-Fi** is also gated by the `vendor.flock.adb-wifi` property; by itself it needs
  RSA key auth (`ro.adb.secure=1`) on a `user` build — but the `collins` `adb/enable` route
  reaches it without that gate.

## See also
- [Apps](apps.md) · [Backend protocol](backend-protocol.md) · [Security posture](security-posture.md) · [Crash logs](crash-logs.md)
