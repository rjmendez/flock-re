# OTA & updates

How firmware/app updates reach the camera, and why the integrity chain is weak.

## Flow
- The updater app fetches the package over HTTPS (chunked range GET from a presigned cloud
  storage URL); metadata/control is on the device-management API
  (`/api/v4/device/{id}/systemPatch`, with a legacy fallback). See [Backend protocol](backend-protocol.md).
- This unit had actually **staged a real update to camera-OS 2.20.0** — forensically confirmed in
  the cache partition: a bootloader control block (BCB) command plus the package path
  `/data/recovery/2.20.0-user.zip`, moving the build number `2019000 → 2020000`. The package is an
  **AOSP legacy full-image ZIP** (not an A/B streaming payload).

## Integrity — bypassable
- **App-level check is SHA-256 only** — the app compares the file hash to a hash from the *same*
  server response. That's an integrity check against corruption, **not** a signature.
- **Real signature check is in recovery.** `/sbin/recovery` verifies the package with a
  **whole-file RSA-2048 / SHA-256** signature against one compiled-in key (`/res/keys`), matching
  `otacerts.zip`. The key is **Flock-self-generated** (`emailAddress=null@flocksafety.com`), not the
  platform key.
- **Why it's weak:** the [bootloader is unlocked and trusts the public AOSP test key](boot-chain.md),
  so an attacker with physical access can flash a modified recovery — moving the goalposts on the
  only real verifier. There is also **no anti-rollback floor** (no AVB2 rollback index), so older
  vulnerable versions can be reinstalled.

## Downgrade / stale fallback (`*bak`)
- The `systembk`/`vendorbk` partitions hold a **complete, bootable, but ~26-month-older** firmware
  image (measured build-date gap between the primary and backup copies). This looks like a
  write-once factory **fallback**, not a live A/B slot kept in sync by OTA *(inference — a true
  active A/B slot would track the primary closely; the large age gap argues against it)*.
- Because there is no rollback floor, a **downgrade installs cleanly**: an attacker (or a pushed
  update) can move the device back to the much older image and re-expose every vulnerability fixed
  in the intervening two years. The newer primary had also dropped 8 Flock privileged apps that
  still exist in the backup.

## See also
- [Backend protocol](backend-protocol.md) · [Boot chain](boot-chain.md) · [Security posture](security-posture.md)
