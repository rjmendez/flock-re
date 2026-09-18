# Device simulation & API-attack sandbox

Turn the **static** firmware findings into **dynamic, reproducible proof** — entirely in a
local sandbox. Nothing here ever touches a real Flock host or uses a real credential
against a real endpoint. It exists to *demonstrate* how the camera's own protocols behave,
for research and disclosure.

> **Hard boundary:** SANDBOX ONLY. The mock server binds localhost; the client connects to
> your own mock. Do not point a real device at a real host; do not replay a real token
> anywhere. Credential validity stays untested by design.

## What's here (runs anywhere, stdlib Python 3)
| File | What it does |
|---|---|
| `upload_server.py` | A **mock of Flock's capture-upload server** — the raw-TLS binary protocol reversed from `ConnectionClient`. Logs everything a device sends and is a target you can attack/fuzz. |
| `upload_client.py` | A **client/attacker** that speaks the same protocol: `--` normal replay of a realistic capture upload, or `--fuzz` to send malformed frames at the parser. |
| `gen_cert.sh` | Self-signed TLS cert for the mock (the device does no cert pinning, so any cert works). |

### The reversed wire protocol (from `flock-st-germain/ConnectionClient`)
Single-byte opcodes; 8-byte **big-endian** length prefixes (`ByteBuffer.putLong`); SHA-256; 2800-byte chunks.

| Opcode | Meaning | Opcode | Meaning |
|---|---|---|---|
| 1 | OK / ack | 6 | FILE contents (len + chunks) |
| 2 | HELLO (carries the auth token) | 7 | HASH (32-byte SHA-256) |
| 3 | protocol version marker (v3) | 8 | UPLOAD_SAVE |
| 4 | SESSION start/end | 9 | UPLOAD_COMPLETE |
| 5 | UPLOAD_START | 12 | METADATA (len + JSON) |

### Run it (verified)
```bash
bash gen_cert.sh server.pem
python3 upload_server.py --port 8443 --cert server.pem &   # mock API
python3 upload_client.py --port 8443 --token SANDBOX-FAKE-TOKEN --size 9000   # normal upload
python3 upload_client.py --port 8443 --fuzz                # attack the parser
```
**Verified results (this repo):**
- Normal round-trip completes: HELLO+token → metadata → chunked file → **server-side SHA-256 verified (match)**. The server log captures the auth token, the detection metadata JSON, and the media bytes — i.e. exactly what a camera transmits.
- **Fuzzing found an unchecked-length allocation DoS:** a `METADATA`/`FILE` frame declaring an enormous length makes the length-prefixed reader attempt to allocate/read it — the mock (faithful to the reversed parser) hit `MemoryError`. Truncated frames hang the blocking reader. The device's parser uses the same trust-the-length pattern.

## Emulator + Frida (provided, run on a host with `/dev/kvm`)
A hardware-accelerated Android emulator needs nested virtualization, which this WSL2 box
lacks (`/dev/kvm` absent), so these are **scripted and syntax-checked here, meant to run on
a KVM-capable host** (e.g. a Linux box or the Windows side running the Android emulator):
| File | What it does |
|---|---|
| `provision_avd.sh` | Create an Android 8.1 (API 27) AVD and install the extracted Flock APKs (all ship `debuggable="true"`). |
| `frida_hooks.js` | Frida hooks for `ConnectionClient` (dump the upload token/metadata live) and `NativeML` (observe the on-device detect/localize calls). |

**Methodology:** boot the AVD → install the Flock APKs → because there is **no cert
pinning**, redirect the app's configured hosts to your mock (hosts file / local DNS) → run
the app under Frida → watch the device perform the real HELLO/metadata/upload against your
mock, and hook `NativeML` to confirm the detect-but-don't-OCR behavior. The full-hardware
image will not cold-boot in an emulator (Qualcomm HALs / camera / modem / TrustZone); all
the interesting logic lives in the app + native layer above the HALs.

## What this proves (maps to the wiki)
- The **binary upload protocol** shape and that it carries the static per-device token → [backend-protocol](../../docs/wiki/backend-protocol.md).
- An **unchecked-length DoS** class in the upload parser (dynamic).
- The path to confirm **OCR is server-side** live (hook `NativeML`, see no text return) → [alpr-pipeline](../../docs/wiki/alpr-pipeline.md).
