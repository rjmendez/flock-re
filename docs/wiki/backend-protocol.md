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

## Capture upload (not HTTP)
- **Not** an HTTP `/v1/sax` multipart endpoint (prior guess corrected). It's a **hand-rolled
  binary protocol over a raw TLS socket** on a dedicated TCP port:
  `HELLO → UPLOAD_START → UPLOAD_METADATA → UPLOAD_HASH → UPLOAD_SAVE → BYE`, with SHA-256
  file-hash verification.

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
Battery/heater/power (voltages, currents, temps), `storage_wear_level`, `fw_version`,
`board_version`, charger state — **and encryption-status fields** (`encryption`, `encrypted`,
`luksVersion`, `cipherName`, `cipherMode`). The device *reports* an encryption posture to the
backend even though the media key is stored in the clear. See [Security posture](security-posture.md).

## Transport security
- **No certificate pinning** in any examined app (no Network Security Config; `CertificatePinner`
  present only as unused library code).
- The custom-TLS upload path builds an `SSLContext` from a bundled keystore, then **returns the
  default context instead** — discarding its own trust material.

## Telemetry
- Operational logs go to a **third-party monitoring service (EU region)**, tagged with the
  device serial in plaintext.

> Documentation of the artifact only — this project never contacts these services.

## See also
- [Apps](apps.md) · [Local attack surface](local-attack-surface.md) · [Data & storage](data-and-storage.md) · [Security posture](security-posture.md)
