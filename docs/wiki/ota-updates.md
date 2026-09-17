# OTA & updates

How firmware/app updates reach the camera, and why the integrity chain is weak.

## Flow
- The updater app fetches the package over HTTPS (chunked range GET from a presigned cloud
  storage URL); metadata/control is on the device-management API
  (`/api/v4/device/{id}/systemPatch`, with a legacy fallback). See [Backend protocol](backend-protocol.md).
- This unit had actually **staged an update to camera-OS 2.20.0** (the expected path appears in
  the cache partition).

## Integrity — bypassable
- **App-level check is SHA-256 only** — the app compares the file hash to a hash from the *same*
  server response. That's an integrity check against corruption, **not** a signature.
- **Real signature check is in recovery.** `/sbin/recovery` verifies the package against one
  compiled-in **RSA-2048** key (`/res/keys`), matching `otacerts.zip`. The key is
  **Flock-self-generated** (not the platform key).
- **Why it's weak:** the [bootloader is unlocked and trusts the public AOSP test key](boot-chain.md),
  so an attacker with physical access can flash a modified recovery — moving the goalposts on the
  only real verifier. There is also **no anti-rollback floor** (no AVB2 rollback index), so older
  vulnerable versions can be reinstalled.

## See also
- [Backend protocol](backend-protocol.md) · [Boot chain](boot-chain.md) · [Security posture](security-posture.md)
