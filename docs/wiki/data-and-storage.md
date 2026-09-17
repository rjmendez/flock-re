# Data & storage

Where the device keeps things. **Structure only** — never the contents of captured media or
personal records, and never secret values.

## Partitions
- **`media` (18 GiB):** captured image/video store — **unencrypted**. `53_media.img` is a normal,
  mountable **ext4** filesystem (plaintext superblock, no `encryptable` flag in `fstab`, no ext4
  encrypt feature bit). The advertised "media encryption" never runs — see below and
  [Security posture](security-posture.md). Readable by anyone holding the device; **not extracted
  or redistributed here.**
- **`userdata` (6.1 GiB):** app working data — **encrypted**. Uses real Qualcomm hardware-backed
  full-disk encryption (`forceencrypt=footer`, opaque image, `libcryptfs_hw.so` with
  ICE/QSEECOM/Keymaster). Not carved. So the vendor encrypts its own app data but leaves the
  captured surveillance imagery in the clear.

## The "media encryption" is decorative
The apps expose an `encryptMediaPartition()` API, but no code path actually encrypts `/media`:
the board-matched implementation is a literal `return true;`, a second is self-documented as
unimplemented, the third only flips a property with a fail-open default — and there is **no
`cryptsetup`/`dmsetup`/LUKS tooling anywhere** in `/system` or `/vendor`.
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
