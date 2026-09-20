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

## Diagnostics (high)
- **Static upload credential logged in cleartext.** A per-device client-auth token that
  authenticates every media upload is written to the logs in full ~**3,906 times** over 6+
  months, at ordinary log level — so it ships inside every crash pack (which are exposed via
  an unauthenticated endpoint, CVE-2025-59403). Unreported publicly. That same static token
  (`CoreValues.authToken`) is reused, unchanged, as the `X-AUTH-TOKEN` bearer for the phone-home/
  telemetry REST API (`api/v1/camera/status`, `heartbeat`, `oneShot`, `settings`, and
  `api/v1/site/settings`) — so one leaked token (e.g. pulled from a crash-pack log) lets a holder
  forge that specific camera's live telemetry, location, health status, and remote
  settings, not just impersonate its media uploads. See [Crash logs](crash-logs.md),
  [Backend protocol](backend-protocol.md).
- **Other secrets in logs** — password strings and live LTE cell-tower IDs (`modemInfo.txt`).

## Deeper pass (surface expansion)
- **Unauthenticated servicing server** (`collins` :8080, system UID, 21 routes incl. ADB→RCE and
  ALPR-DB exfil), reachable over an installer Wi-Fi AP with a hardcoded key. See [Local attack surface](local-attack-surface.md).
- **Backend can overwrite any camera setting** (no signature) and mint fleet credentials from a
  MAC alone. See [Backend protocol](backend-protocol.md).
- **Test-signed secure world** (TZ/keymaster/aboot carry test certs) → key-attestation forgery /
  re-provisioning; `/persist` holds attestation keys. See [Boot chain](boot-chain.md).
- **"Deleted" media may be recoverable** — an archive DB retains records and a OneShot "reprocess"
  path can republish; retention is remote-config with no minimum.
- **Fleet telemetry to Datadog** — a public RUM client token embedded in 8+ apps, every log event
  tagged with the device serial (redacted).
- **Cellular MITM avenues** — eSIM shared-profile TOFU failover after ~10 min LTE loss, and an
  `ApnHelper` APN-injection path with no user consent; Sierra modem firmware updates lack
  signature/rollback checks. See [Cellular & location](cellular-and-location.md).
- **Persist survives factory reset** — device serial embedded in a JWT claim, provisioning
  timestamp, and diagnostics history cross the reset boundary. Now confirmed by code path, not
  just by inspecting the persist image: the two reset triggers — a default-off "Rescue Party"
  watchdog escalation, and an always-on, ungated backend `factory_reset` one-shot command — both
  only ever broadcast the standard Android `FACTORY_RESET` intent, which this device's
  `recovery.fstab` never maps to a `/persist` volume. So the Auth0 client credential and cached
  bearer JWT on `/persist` survive by structural omission (no fstab entry, no wipe-code string
  reference), not by any deliberate persist-wipe carve-out being skipped. See
  [Data & storage](data-and-storage.md).

## Deeper pass II (8-area deep-think)
- **All 5 public GainSec CVEs reproduce against this dump** — CVE-2025-47822/47823/47824 and
  59403/59405 each map to concrete code/config in this image (independent confirmation, not just
  citing the advisory). See [Local attack surface](local-attack-surface.md), [Crash logs](crash-logs.md).
- **DSP reflash / model-injection surface.** The Hexagon DSP FastRPC skeleton
  (`libFastRPC_UTF_Forward_skel.so`) exposes ~42 methods across 28 slots including **unvalidated
  touch-controller firmware reflash**, **custom ML-model injection**, and AFE debug-register access
  (an "AUE" method group repurposed for CV/ML). Reachable from the app processor *(static-only;
  parameter validation unconfirmed at runtime)*.
- **Kernel is a soft target.** kernel 3.18.71 (patch level frozen 2018-06-05) compiles in the
  futex/netfilter/XFRM/ION subsystems that carry published local-privesc CVEs, with **no SMEP/SMAP
  and no KASLR** — so any reachable kernel bug is a direct root escalation *(plausibility by
  version/config, static-only)*. See [Kernel & drivers](kernel.md).
- **Clean downgrade.** No anti-rollback floor + a bootable 26-month-older backup image = an
  attacker or a pushed update can revert the device to firmware missing two years of fixes. See
  [OTA & updates](ota-updates.md).
- **Reliability telemetry leak (temporal).** Across 6+ months of logs the media-upload auth token
  never rotated (value redacted), and firmware 2.9.0→2.12.0 cut logged HTTP upload errors ~86% — a
  measurable backend-reliability signal derived purely from the leaked device logs. See
  [Crash logs](crash-logs.md).

## Cross-cutting
- **Stale software** — patch level frozen 2018-06-05 on a 2025 build. See [Android userland](android-userland.md).
- **Bulk collection (privacy)** — captures all passing vehicles/bystanders, not just watchlist hits.
- **Model IP** — production ML detectors ship unencrypted and unobfuscated. See [ML models](ml-models.md).

## Prioritized attack chains (reporting update)
- **Chain A (highest priority): local app -> credential disclosure -> upload/telemetry impersonation -> transport interception risk.**
  - Runtime disclosure surfaces: exported `SettingsContentProvider` and plaintext token logging.
  - Protocol amplifier: weak endpoint-verification/TLS-context handling in upload transport paths.
  - Operational impact: device identity replay and forged camera-origin traffic become materially easier.
- **Chain B: local app -> unauthenticated database export -> metadata staging -> follow-on abuse.**
  - Runtime disclosure surface: exported `DatabaseExportReceiver`.
  - Impact: sensitive metadata exfiltration and attacker visibility expansion.
- **Chain C: local app -> world-writable root daemon socket -> control/heartbeat injection.**
  - Privilege-boundary surface: `reaperd` socket permissions and unauthenticated message framing.
  - Impact: local process can attempt root-service control-plane manipulation.

### Hardening order
1. Enforce strict transport authentication (correct SSL context usage + endpoint verification).
2. Close credential leaks (provider export/permission model and token logging).
3. Restrict unauthenticated local export/control surfaces (`DatabaseExportReceiver`, `reaperd` socket).

## Execution/tooling update (B2B-gated)
- **Completed lanes (execution-grounded):**
  - protocol state-order/replay probing against the local upload mock (bounded campaign),
  - SELinux policy reachability proof for the export chain (`untrusted_app_all` -> `media_rw_data_file`),
  - token-surface abuse checks in the sandbox chain model,
  - OTA/app-layer update-path review (endpoint + hash/rollback behavior in available artifacts).
- **Runtime-blocked lanes (now with concrete blocker proof):**
  - reaperd wire probe: attached target lacked the required UNIX-socket probe transport path
    for the current harness and no validated reaperd runtime socket was reachable.
  - camera-daemon boundary probe: expected camera runtime socket path was absent on the attached
    emulator target.
- **Method update:** acceptance criteria now require explicit B2B evidence per lane (command,
  artifact path, key output) before findings are promoted beyond *likely*.

## Boundaries of this project
No contact with any live service; no credential used against any endpoint (validity untested by
design); captured media/personal records never extracted. For education and responsible
disclosure only.

## See also
- [Boot chain](boot-chain.md) · [Local attack surface](local-attack-surface.md) · [Backend protocol](backend-protocol.md) · [Data & storage](data-and-storage.md) · [Non-Android protocol fuzz research](non-android-fuzz-research.md)
