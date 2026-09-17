# Security posture

Confirmed observations from static analysis of the public leak. No exploit code; secret
values and hostnames redacted. Severity is the reviewers' static assessment; where a claim
depends on runtime/backend behavior it's marked *(static-only)*.

## Root of trust — defeated (critical)
- **Test-signed secure boot.** The whole Qualcomm secure-world chain (TrustZone, Keymaster,
  lksecapp, RPM, aboot) validates only against a generic Qualcomm **SecTools TEST** chain
  (`OEM_ID=0000`, DEBUG fuse set). `aboot` also trusts the **world-public AOSP `testkey`** to
  verify `boot`/`recovery` — anyone can sign a boot image it will accept. See [Boot chain](boot-chain.md).
- **Bootloader unlocked.** This unit's `devinfo` is byte-confirmed `is_unlocked=1`, with legacy
  per-partition dm-verity (not AVB2) that can be disabled. A physical-access holder can flash
  attacker-controlled kernel/system over USB.

## On-device software (high/critical)
- **Exported auth service.** An OAuth key service is exported with no permission — any app on
  the device can request live tokens/secrets from it. See [Local attack surface](local-attack-surface.md).
- **Unauthenticated identity overwrite.** A broadcast receiver with no permission lets any
  on-device sender overwrite the camera's stored sign-in identity.
- **Fleet-wide hardcoded key.** One API key (value redacted) is compiled identically into every
  device, usable as a legacy-auth fallback. See [Backend protocol](backend-protocol.md).
- **Plaintext credential stores.** Cached tokens/passwords sit in plaintext in on-device
  databases and in `/persist` JSON. See [Data & storage](data-and-storage.md).
- **Capture store is encrypted, but the key is in the clear (proven decryptable).** The media
  `android_expand` volume is real dm-crypt (`aes-128-cbc-essiv:sha256`), but its 16-byte AES key
  is stored **in plaintext beside it** — decryption was **verified** (the ext4 superblock
  recovers), so any device holder can read all captured footage. A *separate* app-level
  `encryptMediaPartition()` layer is a decorative no-op. Meanwhile `/data` is properly
  hardware-key-wrapped FDE whose key is **not** recoverable from the dump — so the vendor
  protects its own app data better than the surveillance imagery. See [Data & storage](data-and-storage.md).
- **Unauthenticated on-device HTTP control server.** One app runs an embedded HTTP server,
  triggerable by an unauthenticated broadcast, exposing reboot, ADB-over-Wi-Fi toggle, live-view
  toggle, and factory-reset. See [Local attack surface](local-attack-surface.md).
- **Full capture-DB exfil via exported receiver.** Another app's exported (no-permission)
  receiver copies the entire ALPR capture database to a shared path on a broadcast.
- **All apps ship `debuggable=true`** in production; a factory test-harness app with open
  exported services ships in the production image; a second default API key (value redacted)
  and cross-app permissions declared `normal`/undeclared widen the on-device surface.

## Native memory safety (critical/medium)
- **Integer overflow → out-of-bounds** in the image-utility library's YUV size check (a 32-bit
  `w*h*3/2` multiply can wrap), reachable from camera-frame data. See [ALPR pipeline](alpr-pipeline.md).
- **Process-kill DoS** — the on-device OCR init calls `exit(1)` on malformed parameters, killing
  the host process.

## Transport & radio (medium/high)
- **No TLS pinning** anywhere in the examined apps; the one custom-TLS path builds then discards
  its own trust material. See [Backend protocol](backend-protocol.md).
- **Baseband** version predates the fix for a published LTE NAS integrity-bypass CVE
  (rogue-base-station class, CVSS 9.8) — *(plausibility by version/date, static-only)*. See
  [Cellular & location](cellular-and-location.md).
- **OTA integrity bypassable.** The app-level update check is SHA-256-only (no signature); real
  RSA-2048 verification lives in recovery — but the unlocked, test-key bootloader accepts a
  reflashed recovery, and there's no anti-rollback floor. See [OTA & updates](ota-updates.md).

## Diagnostics
- **Secrets in plaintext logs.** The gzipped crash packs in the capture store contain app
  logs with a **bearer token** and **password** strings in the clear, plus live LTE
  cell-tower IDs in `modemInfo.txt`. See [Crash logs](crash-logs.md).

## Cross-cutting
- **Stale software** — patch level frozen 2018-06-05 on a 2025 build. See [Android userland](android-userland.md).
- **Bulk collection (privacy)** — captures all passing vehicles/bystanders, not just watchlist hits.
- **Model IP** — production ML detectors ship unencrypted and unobfuscated. See [ML models](ml-models.md).

## Boundaries of this project
No contact with any live service; no credential used against any endpoint (validity untested by
design); captured media/personal records never extracted. For education and responsible
disclosure only.

## See also
- [Boot chain](boot-chain.md) · [Local attack surface](local-attack-surface.md) · [Backend protocol](backend-protocol.md) · [Data & storage](data-and-storage.md)
