# Backend protocol

How the camera talks to the vendor cloud. **All hostnames/URLs are obfuscated** — shape only,
no live addresses.

Flow:
1. **Sign in** — OAuth2 to the vendor auth service (`https://<auth-host>/oauth/token`), using
   an on-device client credential; receives an access token (JWT). Credential/token handling
   is described at rest only in [Data & storage](data-and-storage.md); validity is untested.
2. **Report** — the [upload app](apps.md) POSTs detections/media to a device API
   (`https://<control-host>/api/<v>/device/{id}/…`) authenticated with the token.
3. **Update** — the [updater app](apps.md) pulls OTA packages from an update endpoint on the
   same API surface.
4. **Telemetry** — operational health/logs go to a third-party monitoring service (EU region).

Endpoint families observed (paths generalized): device event ingestion, device identity/
credentials, configuration/parameters, applications inventory, OTA/system patch, validation,
relationship/association. Transport is HTTPS; TLS certificate-pinning posture is a
deep-dive item.

> This project documents the protocol's structure only. It does **not** contact these services
> or exercise any endpoint — see [Security posture](security-posture.md).

## See also
- [Apps](apps.md) · [Data & storage](data-and-storage.md) · [Security posture](security-posture.md)
