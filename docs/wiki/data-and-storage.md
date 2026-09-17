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

## More partitions
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
