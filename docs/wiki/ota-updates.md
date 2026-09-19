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
  platform key. Independently re-derived: the low 32 bits of `otacerts.zip`'s cert modulus
  (via `openssl x509 -modulus`) are byte-identical to the first little-endian word of the
  `res/keys` `n[]` array — confirming the match by a method separate from a full word-array
  comparison (`deep/swarm/ota-signing-rollback-verification/FINDINGS.md`).
- **A third, separate trust domain.** This OTA key is neither the [SecTools TEST
  chain](boot-chain.md) trusted by TrustZone/Keymaster/lksecapp/RPM nor the world-public AOSP
  `testkey` that `aboot` trusts for `boot`/`recovery` image signatures — three independent keys
  exist in this firmware, and only this one validates OTA packages. **Correction to a natural
  reading of the boot-chain findings:** a package "signed with the same TEST key chain" [aboot
  and TrustZone trust](boot-chain.md) would actually be **rejected** by recovery's OTA verifier —
  that TEST/testkey material doesn't produce a signature the OTA key accepts. So the OTA key
  itself isn't the weak link here; the real downgrade risk is a different mechanism (see below).
- **Anti-rollback fuse state: unconfirmed.** The secure-world leaf certs carry a Qualcomm `SW_ID`
  field meant to be checked against a monotonic QFPROM fuse counter, but whether that enforcement
  is actually *active* on this chip could not be determined from a static image dump — fuse state
  is a physical, one-time-programmable register. A prior internal claim that "secure boot is
  disabled" on this device is likewise under-evidenced (no cited offset or runtime check backs
  it) and should be read as **unconfirmed**, not fact. This doesn't change the bottom line: the
  bootloader is confirmed **unlocked** and `aboot` accepts the public AOSP testkey regardless of
  fuse state, so a physical attacker doesn't need that question resolved either way.
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

### Companion-app downgrade is explicit, not just unprotected
- The shared version-decision method `UpdateHelper.needsInstallation()` takes an
  `allowDowngrade` flag hardcoded per update-channel caller — **`false`** for the OS image
  (`UpdateHelperAndroidOs`) and external accessory firmware (`UpdateHelperPenguinPack`), but
  **`true`** for every regular companion Android app (`UpdateHelperAndroidApp` — the
  camera-capture app, sensor service, ALPR pipeline, phone-home app, settings-service, and the
  updater itself).
- That's backed up at the actual install call, not just the "should I fetch this" decision: both
  real companion-app install sites (`UpdateTask.installNative()` and `RollbackHelper`'s
  self-rollback path) pass `installFlags = 130` (`0x82` = `INSTALL_REPLACE_EXISTING` `0x02` |
  `INSTALL_ALLOW_DOWNGRADE` `0x80`) to the hidden system `PackageManager.installPackage()` API —
  deliberately turning off Android's own downgrade protection for **every ordinary companion-app
  install**, not just an explicit rollback feature.
- This doesn't bypass Android's own APK-signature enforcement — a downgraded package still has to
  carry the same signing cert `PackageManager` independently checks — so it's **not** a path to
  unsigned code. It **is** a code-confirmed mechanism to roll any companion app back to any
  older, authentically-signed, potentially-vulnerable release the backend is willing to advertise
  as the target version. Not tested against a live backend (out of scope, no network contact): the
  on-device downgrade gate is **off by design** for companion apps — a code-level finding, not a
  demonstrated remote exploit today. See
  `deep/swarm/ota-signing-rollback-verification/FINDINGS.md`.

## See also
- [Backend protocol](backend-protocol.md) · [Boot chain](boot-chain.md) · [Security posture](security-posture.md)
