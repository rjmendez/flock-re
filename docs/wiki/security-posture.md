# Security posture

High-level, factual observations for understanding trade-offs. No exploit detail; consistent
with prior public reporting. Static analysis of a public leak only.

- **Stale software.** Built 2025-06-05 but Android security-patch level is **2018-06-05** —
  ~7 years of unpatched, publicly-known AOSP/kernel vulnerabilities. See [Android userland](android-userland.md).
- **Secrets at rest.** OAuth client credential + cached tokens stored in cleartext in
  [`persist`](data-and-storage.md). Validity **untested by design**; values never published.
- **Boot integrity.** Public teardowns of this class report an unlocked bootloader and
  non-production (test-key) signing — see [Boot chain](boot-chain.md).
- **Media key.** Prior researchers reported an unencrypted media-decryption key on-device.
- **Bulk collection (privacy).** ALPR captures *all* passing vehicles and bystanders, not just
  watchlist hits — the core privacy concern is the indiscriminate collection itself.

## Boundaries of this project
- No contact with any live service; no use of any credential against any endpoint.
- Media contents and personal records are never extracted or published.
- Findings are for education and responsible disclosure, not offense.

## See also
- [Data & storage](data-and-storage.md) · [Backend protocol](backend-protocol.md) · [Boot chain](boot-chain.md)
