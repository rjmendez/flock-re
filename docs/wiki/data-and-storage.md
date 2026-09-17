# Data & storage

Where the device keeps things. **Structure only** — never the contents of captured media or
personal records, and never secret values.

## Partitions
- **`media` (18 GiB):** captured image/video store. On this dump it's a high-entropy
  `android_expand` volume (looks encrypted), most likely under AOSP vold's default per-volume key
  — but note the media-encryption routine is a **no-op on this device's code path**
  (see [Security posture](security-posture.md)). Not extracted or redistributed here.
- **`userdata` (6.1 GiB):** app working data. On this dump it does not parse as a plain
  filesystem (high entropy) — treated as encrypted/opaque; not carved.
- **`persist` (32 MiB):** device identity/settings, survives factory reset. Holds the OAuth
  client credential + token as **plaintext JSON** under `/persist/<vendor>/auth0/`. No SQLite or
  shared_prefs here; the DRM/keystore skeleton dirs are empty on this unit.

## On-device databases (schemas recovered from app code, not from userdata)
The apps use Room (SQLite); the `CREATE TABLE` SQL is embedded in the app code, so schemas are
readable even though `userdata` is opaque:
- **ALPR capture pipeline:** `sessions`, `assets`, and per-stage timing tables.
- **`core_values`** (settings app): stores `auth_token` as **plaintext TEXT**, alongside serial
  number and upload/status URLs.
- **`accessory`** (system-control app): stores `auth_password` / `auth_token` as **plaintext
  TEXT** for paired hardware accessories.

For privacy this project reports schemas/table names only — never row contents. Raw secret
values are never published.

## See also
- [Backend protocol](backend-protocol.md) · [Security posture](security-posture.md) · [Partition map](partition-map.md)
