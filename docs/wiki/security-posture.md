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
- **Media encryption no-op.** On this device's selected code path the "encrypt media partition"
  routine does nothing (returns success without acting); a sibling board variant fails *open* on
  an unset flag. *(static-only for effect)*

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
