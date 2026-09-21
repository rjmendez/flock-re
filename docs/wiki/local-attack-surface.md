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

## Chained attack paths & signing-certificate boundary
- **All ~20 system APKs share one signing certificate — this does not narrow the surface above.**
  amarula, ciroc, sambuca, sensor, motion, settings, system-control, collins, phone-home,
  st-germain, updater, quality-control, assembly-validator, medalla-light, cachaca, big-boi-bud,
  peripheral, encoding, and remotesimlockservice all carry the **identical** signer cert
  (SHA-256 `62:BC:03:B1:AF:24:17:1B:CC:79:2B:A5:7A:9B:AF:4C:A1:A6:78:FE:AD:84:56:33:83:C1:A5:5F:31:86:18:9A`,
  subject `O=Android/.../emailAddress=null@flocksafety.com`) and all declare
  `sharedUserId="android.uid.system"`. That's a real, verified fact about this build, but none of
  the exported components already listed above (`Auth0KeyService`, `ciroc`, amarula's
  `DatabaseExportReceiver`, `SensorContentProvider`, `OneShotReceiver`) are gated by a
  `protectionLevel="signature"` permission — they're either fully ungated or `normal`, which is
  auto-granted to any app at install regardless of who signed it. Co-signing with Flock buys an
  attacker nothing extra here.
- **A previously-undocumented exported provider: `flock-settings`' `SettingsContentProvider`.**
  Exported, gated only by a `normal`-level permission (`settingsservice.provider.WRITE`) — and
  because that's a single `android:permission` attribute rather than split read/write
  permissions, it also gates reads. Any app holding that (auto-granted) permission can query it
  for the `core_values` row (auth token, serial number, upload URL). That harvested serial+token
  is exactly what the binary upload protocol's `HELLO` frame needs (see
  [Backend protocol](backend-protocol.md)), letting the holder open the same upload session and
  be indistinguishable from the real camera for that session. This is a **spoofing/injection
  primitive** (forge or replay sessions, push fabricated `UPLOAD_SAVE` payloads) — the protocol
  has no read/download opcode, so it doesn't pull the camera's own already-uploaded data back out.
- **The lowest-effort path to live ALPR/location data needs no chaining at all.** The
  already-documented amarula `DatabaseExportReceiver` (or its `AssetContentProvider`) is reachable
  in a single unguarded local hop — no Auth0 token, no HELLO token, and no co-signing with Flock
  required.
- **One sibling provider is dead code (positive/scoping note).** amarula's
  `MediaDBInfoContentProvider` declares a `READ_MEDIADBB_INFO` permission gate, but that exact
  string is never declared by any `<permission>` tag anywhere in the extracted image (likely a
  shipped typo of `READ_MEDIADB_INFO`). Despite looking identically configured to its siblings, no
  app — including a co-signed Flock app — can ever hold that permission, so this one provider is
  effectively unreachable.
- **Open question — SELinux.** Whether these `sharedUserId=android.uid.system` domains are
  actually reachable from a third-party `untrusted_app` SELinux domain could not be confirmed from
  this dump (no `seapp_contexts` file or `sesearch`/`seinfo` binary present). Flagged as open, not
  asserted either way — a live-device test would be needed to resolve it.

Evidence: decompiled manifests/code paths and local tool notes referenced in this wiki.

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
