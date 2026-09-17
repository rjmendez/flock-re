# Flock ALPR camera — firmware wiki

Structural notes on a Flock Safety "Falcon" ALPR camera, from the public DDoSecrets
firmware leak. Static analysis only. Backend hostnames and all secrets are obfuscated.

## Device
- [Hardware](hardware.md)
- [Cellular & location](cellular-and-location.md)
- [Security posture](security-posture.md)

## Firmware layout
- [Partition map](partition-map.md)
- [Boot chain](boot-chain.md)
- [Android userland](android-userland.md)
- [Data & storage](data-and-storage.md)

## Software
- [Apps](apps.md)
- [ALPR pipeline](alpr-pipeline.md)
- [ML models](ml-models.md)
- [Backend protocol](backend-protocol.md)

## Reference
- [Glossary](glossary.md) — plain-language terms

---
Conventions: each note is short and factual, links related notes under **See also**, and
redacts hostnames as `<role-host>` and secrets entirely. Sizes/versions are from this one
dump and may vary by unit/build.
