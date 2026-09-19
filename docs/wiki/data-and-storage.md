# Data & storage

Where the device keeps things. **Structure only** — never the contents of captured media or
personal records, and never secret values.

## Partitions
- **`media` (18 GiB):** the ALPR capture store. The partition (`53_media.img`) is a *plaintext*
  ext4 container, but the captures themselves live inside a `virtual_disk` file — a GPT image
  whose `android_expand` volume **is dm-crypt encrypted** (`aes-128-cbc-essiv:sha256`, ext4
  inside). **The catch:** the 16-byte AES key is stored **in plaintext right beside it**
  (`expand_….key`). Decrypting the volume with that key was **verified** — the ext4 superblock
  recovers cleanly — so **anyone holding the device can decrypt all captured footage.** Only the
  superblock (metadata) was decrypted here to prove it; capture contents are never extracted.
- **`userdata` (6.1 GiB):** app data — **properly encrypted.** Legacy FDE (`forceencrypt=footer`)
  with genuine Qualcomm ICE/QSEECOM hardware key-wrap (`libcryptfs_hw.so`). Unlike media, **its
  key is not recoverable from the dump**: the crypt-footer magic is absent from the whole image,
  `keystore` is zero-filled, and no key blob was found across ~34 GB of partitions.

The two volumes are handled very differently: `/data` is hardware-bound (key not present in the
dump), while the capture store is encrypted with its key left in the clear.

## Two encryption layers — one real-but-defeated, one decorative
- **Adoptable-storage dm-crypt (real, but undone by key handling):** vold encrypts the media
  `android_expand` volume with AES-128; the key sits unprotected on the plaintext container, so
  the encryption provides no protection against a device holder. (Proven with a superblock-only decryption script — no capture content.)
- **App-level `encryptMediaPartition()` API (decorative):** a *separate* layer the apps expose —
  the board-matched implementation is a literal `return true;`, a second is unimplemented, the
  third fails open, and there's no `cryptsetup`/LUKS tooling. Non-functional.

## What's in the capture store (decrypted, metadata only)
Decrypting the `android_expand` volume's ext4 and walking it (metadata only, no frame
data) shows:
- **~27,321 `.mp4` video files, ~13.2 GiB** — the captures are **video, not stills** (which is
  why EXIF-JPEG scans found nothing). Laid out under `/media/0/media/` in per-session dirs.
- **4 gzipped crash dumps** (`.pak`, ~165 MiB) in `/media/0/media/crashpack/`, spanning
  2025‑07 → 2026‑01 — gzip (`1f8b08`), i.e. crash/diagnostic packs, **not yet opened**.
- **Video metadata:** each MP4 carries a `moov` with `mvhd` **creation_time** and a
  `meta`→`keys`/`ilst` tag block + handler info; the sampled file had **no in-file GPS**
  (`©xyz`/`loci`) atom. Geolocation travels out-of-band in the [upload `Location` record](backend-protocol.md),
  not the video container. (One sample; values redacted.)

## More partitions
- **`persist` (32 MiB):** device identity/settings, survives factory reset. Holds the OAuth
  client credential + token as **plaintext JSON** under `/persist/<vendor>/auth0/`. No SQLite or
  shared_prefs here; the DRM/keystore skeleton dirs are empty on this unit. See below for the
  reset code paths that explain *why* this survives.

## Factory reset / decommission: what survives
There is no bespoke Flock "RMA wipe" or decommission service anywhere in this firmware. Exactly
two code paths ever trigger a reset, and both simply broadcast the stock AOSP
`android.intent.action.FACTORY_RESET` intent — funneling into the OS's own `MasterClearReceiver` /
`RecoverySystem.rebootWipeUserData()` machinery, not a Flock-reimplemented wipe routine:
1. **Automatic "Rescue Party" watchdog escalation** (`RescueActionHandler.factoryReset()`) — gated
   by `persist.vendor.flock.rescue_party.factory_reset_enabled`, shipped `false` in the extracted
   vendor `build.prop` (though remotely re-enablable as a pushed camera setting).
2. **Backend-issued `factory_reset` one-shot command** (`OneShotHandler.handleFactoryReset()`),
   delivered over the same phone-home one-shot channel referenced in [Backend
   protocol](backend-protocol.md)'s "Backend control" section — this one has **no property gate at
   all**, so any `factory_reset` one-shot the backend sends unconditionally wipes the device.

Per this device's own `recovery.fstab`, the wipe flow only knows how to format `/system`,
`/cache`, `/vendor`, `/data` (userdata), `/boot`, `/recovery`, `/misc`, and the `*bk` backup
partitions — there is **no `/persist` entry at all**, and the recovery binary's wipe-command
strings (`wipe_data`, `wipe_cache`, `prompt_and_wipe_data`) have no `/persist` string anywhere
near them. `/persist` is structurally out of scope for every reset path this firmware implements.

**Concrete effect:**
- The Amarula ALPR capture DB (`/data/user/0/.../databases/{live-media-db,media-db}` + WAL files,
  and the world-readable export copy at `/data/media/logs/media-db`) lives under `/data` and **is
  wiped** by a factory reset.
- The cached Auth0 client credential (`auth0_cred`) and bearer JWT (`auth0_token`) at
  `/persist/flock/auth0/` — the exact material needed to make a decommissioned device impersonate
  a still-provisioned camera to the backend — are **not wiped** by any reset path. This confirms,
  by code path (not just by inspecting the persist image contents), the "survives factory reset"
  framing above.

**Separate wipe surface:** a `reformat` one-shot command (distinct from `factory_reset`) can
additionally wipe a native-HAL-managed "media partition" via
`PeripheralController.reformatMediaPartition()` (AIDL transaction 15, gated by
`vendor.flock.media.format`). Nothing in the `factory_reset` path calls this, so a factory reset
alone would not necessarily purge that separately-staged media store — a second, explicit
`reformat` one-shot (`media: true`) would be required. The native peripheral-HAL implementation
wasn't present in this dump, so the exact scope of "media partition" isn't independently
confirmed here — flagged as an open follow-up rather than asserted as fact.

Evidence: `deep/swarm/factory-reset-data-remnants/FINDINGS.md`.

## On-device databases (schemas recovered from app code, not from userdata)
The apps use Room (SQLite); the `CREATE TABLE` SQL is embedded in the app code, so schemas are
readable even though `userdata` is opaque:
- **ALPR capture pipeline:** `sessions`, `assets`, and per-stage timing tables.
- **`core_values`** (settings app): stores `auth_token` as **plaintext TEXT**, alongside serial
  number and upload/status URLs.
- **`accessory`** (system-control app): stores `auth_password` / `auth_token` as **plaintext
  TEXT** for paired hardware accessories.

### What a capture row actually holds (column-level, code-verified)
The `assets` table (Room `@Entity` in `flock-amarula`, written by `flock-object`) has **no
plate-text column**. Its two JSON blobs were traced to their serializer classes:
- **`metadata_ml`** = JSON of `DetectionResults` → per-object `Detection` records whose fields are
  `trackId`, `linkedTrackId`, `linkedDetectionId`, `className` (an object *category* like
  vehicle/plate — not the plate characters), `confidence`, `quality`, bounding box
  (`xmin/xmax/ymin/ymax`), `direction`, `selected` — **no plate-text field**. A grep of the whole
  `ml/lib/models` package for
  `plate|ocr|text|characters|readResult` returns **zero** hits, and `NativeML` exposes no
  text-returning JNI method — so **the plate number is never produced or stored on-device.** This
  is the evidence behind the [server-side OCR](alpr-pipeline.md) finding.
- **`sensor_metadata`** = JSON of `SensorMetadata` = **camera parameters only** (`iso`, `isNight`,
  `expMs`, `wbGains`, `bracketType`, full-res width/height, `cropSettings`, `sensorTimestamp`,
  aspect ratio) — **13 fields, no GPS/lat/lon/IMU.** Per-capture geotagging does **not** happen
  on-device; the camera carries a single fixed location as a system property
  (`persist.vendor.flock.phonehome.location.*`) applied at the [upload layer](backend-protocol.md)
  — consistent with a fixed-mount camera.
- **Save vs upload defaults:** `MlMetadataSettings` ships `SAVE_ML_METADATA=false` /
  `UPLOAD_ML_METADATA=true` — detection metadata is **uploaded by default even when not persisted
  locally** (both remote-config gated).

Reproduce: `tools/schema/extract_capture_schema.sh` (greps the decompiled `Asset`/`Detection`/
`SensorMetadata` classes and prints the field lists + file:line anchors).

For privacy this project reports schemas/table names only — never row contents. Raw secret
values are never published.

## See also
- [Backend protocol](backend-protocol.md) · [Security posture](security-posture.md) · [Partition map](partition-map.md)
