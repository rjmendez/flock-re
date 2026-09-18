# Glossary

Plain-language terms used across the wiki.

- **ALPR** — Automatic License Plate Recognition: finding and reading plates in images.
- **SoC / SoM** — System-on-Chip (the main processor); System-on-Module (a ready-made board
  carrying the SoC, RAM, storage).
- **Partition** — a fixed region of the device's storage with a specific job. See [Partition map](partition-map.md).
- **Bootloader** — early code that starts the device and loads the OS. See [Boot chain](boot-chain.md).
- **TrustZone / secure world (QSEE)** — an isolated, protected execution area on the chip for
  sensitive operations (keys, crypto).
- **Verified/secure boot** — each boot stage cryptographically checks the next; a "test-key"
  or "unlocked" state weakens that guarantee.
- **OTA** — Over-The-Air update: new firmware/apps delivered over the network.
- **OAuth2 / JWT** — a standard sign-in scheme; the token it issues (a JWT) is a signed string
  proving the device may talk to the backend.
- **TFLite** — TensorFlow Lite, the on-device neural-network format. See [ML models](ml-models.md).
- **MSER** — Maximally Stable Extremal Regions, a classic computer-vision technique used here
  for on-device plate **region detection / quality scoring** — *not* character reading. The actual
  plate-number OCR is server-side. See [ALPR pipeline](alpr-pipeline.md).
- **Baseband / MPSS** — the cellular modem's own firmware/processor. See [Cellular & location](cellular-and-location.md).
- **eSIM** — an embedded SIM (no physical card) for cellular service.

## See also
- [Home](Home.md)
