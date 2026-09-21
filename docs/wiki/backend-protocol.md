# Backend protocol

How the camera talks to the vendor cloud, from decompiled code. **Hostnames/URLs and secret
values redacted** — shape only.

## Sign-in (OAuth2)
- Grant: `client_credentials` to the vendor auth service (`https://<auth-host>/oauth/token`).
- Params: `grant_type`, `client_id`, `client_secret`, `audience=<vendor-device-audience>` —
  **no `scope`** (corrects a prior guess).
- Response (`access_token`, `expires_in`, `token_type`) is JSON-parsed; the client_id/secret are
  read and rewritten in **plaintext JSON on `/persist`**. See [Data & storage](data-and-storage.md).
- The real OAuth implementation lives in a dedicated app (`flock-sambuca`) behind an AIDL
  service — which is [exported without permission](local-attack-surface.md).

## Device management API
- Current endpoints are `/api/v4/...` authenticated with the OAuth **JWT bearer**.
- **Every v4 endpoint has a legacy `/api/v1–v3` sibling** using a static per-device
  `x-auth-token` **plus a fleet-wide `x-api-key`** (value redacted), silently selectable at
  runtime by a system property. See [Security posture](security-posture.md).
- Endpoint families (paths generalized): device event ingestion, identity/credentials,
  configuration/parameters, applications inventory, OTA/system patch, validation, association.
- **Phone-home / status REST channel (`GimletService`).** A distinct REST surface (not the
  `/api/v1–v4` device-management API above) carries periodic status/telemetry, heartbeat,
  one-shot tasking, and settings: `api/v1/camera/status`, `api/v1/camera/heartbeat`,
  `api/v1/camera/oneShot/{timestamp}`, `api/v1/camera/status/settings`, and `api/v1/site/settings`
  (HTTP `PUT`). Routes live on a `*gimlet.flocksafety.com`-family host — the default fallback used
  before a camera is provisioned is hardcoded to `https://dev-gimlet.flocksafety.com/` for both
  `statusUrl` and `uploadUrl` (`CameraSettings.java`'s default `CoreValues` row). Every route
  authenticates with two headers: `X-AUTH-TOKEN: <apiKey>` and `X-SERIAL: <serial>`.
- **The static per-device token is shared across both channels, not upload-only.** That
  `X-AUTH-TOKEN` is `CoreValues.authToken` — a single flat field (alongside `serialNumber`/
  `statusUrl`/`uploadUrl` in one SQLite-backed content-provider row, see
  `CameraSettings.getCoreValuesFromContentProvider()`) that is the *same* value the binary upload
  protocol's `HELLO` opcode sends as `auth_token` (see [Capture upload](#capture-upload-not-http)
  below). One static, never-rotated per-device credential authenticates **both** the binary
  media-upload socket **and** this REST telemetry/settings/heartbeat/one-shot API — a leaked token
  compromises both. The default placeholder credential baked into the pre-provisioning fallback is
  `CoreValues.DEFAULT_API_KEY = "dirtymartini"`, matching this project's already-documented
  cocktail-name constant convention (`sambuca`, `cachaca`, `ciroc`, …).
- **Dynamically confirmed, not just inferred.** A dynamic-analysis harness independently
  confirmed, via a live method return on a genuinely-ARM-emulated Android guest running the real
  (only cosmetically re-signed) `flock-object` app, that
  `CameraSettings.getCoreValuesFromContentProvider()` is in fact the runtime source of the
  device's `CoreValues` (serial/auth-token/status-URL/upload-URL) — the same class the static
  analysis above already identifies as backing the phone-home auth token. This is now a
  dynamically-confirmed call path, not only an inferred one from decompiled code. The same live
  run observed the shipped production APK's built-in dev-fallback defaults as literal,
  non-obfuscated placeholder strings — `serialNumber=cereal`, `authToken=dirtymartini`,
  `statusUrl=uploadUrl=https://dev-gimlet.flocksafety.com/` — dynamically confirming, rather than
  only statically reading, the fallback values above. These are non-production placeholders, not a
  live production credential, but are real, dynamically-observed evidence of what a release
  binary's fallback path actually contains. The same run also confirmed live that `flock-object`
  requires `sharedUserId=android.uid.system` (install fails with
  `INSTALL_FAILED_SHARED_USER_INCOMPATIBLE` unless platform-signed), corroborating the static
  manifest finding already covered on [Local attack surface](local-attack-surface.md) /
  [Apps](apps.md). Reproduce: `tools/jni-harness/README.md`.

## Capture upload (not HTTP)
- **Not** an HTTP `/v1/sax` multipart endpoint (prior guess corrected). It's a **hand-rolled
  binary protocol over a raw TLS socket** on a dedicated TCP port:
  `HELLO → UPLOAD_START → UPLOAD_SIZE → UPLOAD_METADATA_SIZE → UPLOAD_HASH → UPLOAD_SAVE → UPLOAD_COMPLETE → BYE` (message constants from `ProtocolConstants`; a session is bracketed by `UPLOAD_SESSION_START`/`UPLOAD_SESSION_END`), with SHA-256
  file-hash verification.

## Protocol robustness (tested against a reversed-protocol mock, not the real device)
To probe how forgiving this opcode-framed protocol's design is to malformed or adversarial input,
a from-scratch mock server was built reimplementing the reversed wire format above (HELLO/SESSION/
UPLOAD_START/METADATA/FILE/HASH/UPLOAD_SAVE/UPLOAD_COMPLETE) and fuzz-tested. **This is a test of a
protocol simulation, not the real device or Flock's real backend** — whether these findings apply
to the real backend implementation is not independently verified. Seven bugs were found via
dynamic testing of the simulation and independently re-verified:

1. A valid, correctly length-prefixed short frame followed by extra bytes in the same write is not
   resynchronized — the extra bytes are dispatched as the next opcode, letting one frame smuggle
   another; an oversized trailing declared length can hang a handler thread forever (no socket
   timeout is ever set).
2. A non-positive declared length (`0`, `-1`, or a large negative value) on HELLO/METADATA/FILE
   short-circuits the body read entirely, yet the frame is still acknowledged as successful — the
   bytes actually sent are then replayed as bogus subsequent opcodes.
3. Opcodes are accepted and acknowledged individually with no session/state tracking and no
   enforced ordering — a full capture sequence sent in reverse order, or with authentication
   skipped entirely, is still acknowledged step by step.
4. The fixed 32-byte HASH frame has no trailing-byte check (extra bytes after it are read as the
   next opcode) and no timeout (withholding the last byte hangs the handler thread forever).
5. ~~The per-upload integrity hash is a single running digest across the whole TCP connection
   rather than reset per capture, so a second legitimate capture on a reused connection spuriously
   fails its hash check.~~ **Retracted mock fidelity gap (non-generalizing):** this was a mock-only fidelity gap, not a confirmed real-device bug. The real
   `ConnectionClient` instantiates a fresh `MessageDigest` as a local variable inside each
   `sendFile()` call (never stored on the object), so a reused connection can never leak one
   capture's hash into the next. This was a mock-only fidelity gap in how the simulation was written,
   not a confirmed real-device bug.
6. HELLO/METADATA string fields are logged verbatim with no sanitization, so embedded CR/LF or
   ANSI/OSC bytes can forge fake log lines or corrupt a tailed terminal.
7. An unbounded one-thread-per-connection accept loop with no per-connection timeout and no
   top-level exception handler besides `KeyboardInterrupt` means enough stalled concurrent
   connections exhausts file descriptors and crashes the whole server process, denying service to
   every client.

These bugs were found via dynamic testing of a protocol simulation built from the reversed wire
format documented above, **not** the real device or Flock's real backend implementation. A
follow-up pass cross-checked all seven against the real client's own code
(`ConnectionClient.java`, identical across all 5 extracted apps): finding 5 is retracted (above);
findings 1/2/4 remain unconfirmed as *specific mechanisms* against the real backend (that server's
source isn't in this dump), but the general pattern they're built on — **trusting an unvalidated
peer-supplied length prefix to size a read or allocation** — is confirmed to be a real, present
habit in Flock's own shipped client code, not something invented for the mock. The client's own
`sendHello()` does exactly this when parsing the *server's* response (unchecked `int` cast on an
8-byte length, plus a non-looping `read()`) — a real, dynamically-uninvestigated bug in the actual
device, written up as finding #8 in the local protocol notes. Reproduce:
`tools/sandbox/upload_server.py` (the mock server) and `tools/sandbox/README.md`.

## What each capture transmits (from the app data models)
Per captured vehicle, the device records/sends structured metadata (field names from the
decompiled models; no values shown):
- **Precise location** — `latitude`, `longitude`, `altitude`, `accuracy` (an `uploadclient`
  `Location` object). The device geotags captures with full GPS.
- **Per-detection** (`Detection`) — object `className` (e.g. licensePlate/vehicle), `confidence`,
  `quality`, bounding box (`xmin/xmax/ymin/ymax`), `direction`, `trackId`.
- **Capture envelope** (`DetectionResults` / `MediaAsset`) — `cameraSerial`, `cameraType`,
  `modelName`/`modelVersion`, `cameraId`, `width`/`height`, `cropInfo`, `licensePlateExposure`,
  `metadataMl`, `createdAt`.

Note: captures carry **no EXIF** (the app and native image code write none — 0 `ExifInterface`
refs); all this metadata rides in the structured records/upload payload, not in the image files.

### Device telemetry (separate health payload)
This is the payload posted over the phone-home REST channel above
(`StatusPayloadCreator.getStatusPayload()`, a ~36.5 KB JSON body sent to `api/v1/camera/status`
every cycle — matching the payload-size figure in [Runtime surface](#runtime-surface-confirmed-from-crash-pack-logs)
below). Confirmed fields:
- **Device/network identity** — device serial (`Build.getSerial()`), IMEI, ICCID/SIM serial
  (`ESIM_ICCID`), baseband/modem firmware version, and per-carrier modem/RIL properties
  (AT&T/Verizon/T-Mobile/Sierra/generic).
- **A full fused-GPS fix every cycle** — `latitude`, `longitude`, `altitude`, `bearing`, `speed`,
  plus accuracy/age fields for each. A `smallPhoneHomePayload` mode trims this to
  lat/lon/accuracy/age only, but GPS is sent either way.
- **Per-LTE-cell detail as a first-class JSON field, `modem.towers[]`** — `pci`, `dbm`, `earfcn`,
  `rsrp`, `rsrq`, `snr`, `registered` per cell, and for the currently registered cell also `cid`
  (Cell ID) and `tac` (Tracking Area Code). This is a stronger exposure than the `modemInfo.txt`
  cell-tower note in [Cellular & location](cellular-and-location.md) / [Crash logs](crash-logs.md)
  — it's sent directly in the primary phone-home body every cycle, not just recoverable from a
  crash-pack log.
- **Asset/detection counts, raw device logs, crash-pack listings, APN info** — plus battery/
  heater/power (voltages, currents, temps), `storage_wear_level`, `fw_version`, `board_version`,
  charger state, and encryption-status fields (`encryption`, `encrypted`, `luksVersion`,
  `cipherName`, `cipherMode`). The device *reports* an encryption posture to the backend even
  though the media key is stored in the clear. See [Security posture](security-posture.md).
- **An `auth0` object with 10-character credential hints, sent every cycle.** `clientIdHint` and
  `clientSecretHint` are the first 10 characters of the device's Auth0 client ID/client secret.
  Ten characters of a typical 32–64-character Auth0 client secret meaningfully narrows the
  brute-force/credential-stuffing search space for anyone who can read the payload.

Transport for this channel is TLS with the platform's default OkHttp/Android certificate
validation — no evidence of the upload protocol's `SSLContext`-discard bug below, but also no
certificate pinning, so the real exposure here is replay/forgery via the shared static token
(above), not passive sniffing.

## Runtime surface (confirmed from crash-pack logs)
Across 6+ months of logs the device's entire network surface is **3 hosts**: two REST APIs
(legacy v1 + v4, used by `phonehomeservice`) and one raw-TLS **binary-upload** socket
(`ConnectionClient`). A ~**36.5 KB** telemetry/status payload posts every cycle (distinct from
the tiny heartbeat). The upload backend self-reports ~**1,950 internal pod IPs** (a large
load-balanced fleet). The binary-upload channel authenticates with a **static per-device token
that never changed** — and is logged in cleartext (see [Crash logs](crash-logs.md)). The
`objects` ML app makes no network calls itself; the OTA source host is never logged.

## Backend control (phone-home behaves like a C2 channel)
The `phonehomeservice` `site/settings` response can **overwrite arbitrary camera settings with no
allowlist and no response signature**, and there is a `oneShot` task channel — so the backend can
reconfigure the device (including `leaveWifiEnabled`, which keeps the servicing AP up) and issue
tasks. Known control actions (reboot, restart-modem) are already public; the arbitrary-setting
overwrite is broader.

## Self-provisioning
A hardcoded fleet API key plus a **MAC-address-only credential endpoint**
(`/api/v3/devices/credentials`) mint OAuth credentials **with no device proof** — a fleet-wide
credential-issuance path, not a per-device secret.

## Transport security
- **No certificate pinning** in any examined app (no Network Security Config; `CertificatePinner`
  present only as unused library code).
- The custom-TLS upload path builds an `SSLContext` from a bundled keystore, then **returns the
  default context instead** — discarding its own trust material.

## Telemetry
- Operational logs go to a **third-party monitoring service (EU region)**, tagged with the
  device serial in plaintext.

> Documentation of the artifact only — this project never contacts these services. The
> protocol-robustness testing above also never contacted any real host — it ran entirely against
> a local mock server.

## See also
- [Apps](apps.md) · [Local attack surface](local-attack-surface.md) · [Data & storage](data-and-storage.md) · [Security posture](security-posture.md) · [Non-Android protocol fuzz research](non-android-fuzz-research.md)
