# Data & storage

Where the device keeps things. This project reports **structure only** — never the contents of
captured media or personal records, and never secret values.

- **`media` (18 GiB):** captured image/video store — the surveillance data itself. Not
  extracted or redistributed here.
- **`userdata` (6.1 GiB):** app working data — SQLite databases, configuration, shared
  preferences, cached sign-in tokens. Documented as schemas/table names only.
- **`persist` (32 MiB):** device identity and settings that survive factory reset. Holds
  vendor auth material under `/persist/<vendor>/auth0/`.

Credential exposure (described, not disclosed): the persist area contains an OAuth client
credential and cached access tokens **in cleartext**. Raw values are never published; validity
is deliberately untested. Public teardowns also report an unencrypted media-decryption key on
this device class — locating it in this dump is a deep-dive item. See [Security posture](security-posture.md).

## See also
- [Backend protocol](backend-protocol.md) · [Partition map](partition-map.md) · [Security posture](security-posture.md)
