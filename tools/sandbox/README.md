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
| `client_server_emulator.py` | Controllable localhost emulator for fuzzing **client-side** behavior (can inject malformed HELLO responses, FAIL acks, and state-transition mismatches without hitting real infrastructure). |
| `client_fuzz_harness.py` | Scenario runner that drives `upload_client.py` against `client_server_emulator.py` and writes per-scenario JSON outcomes under `tools/sandbox/campaign_results/client_harness_*`. |
| `telemetry_sim_capture.py` | Collector/parse pipeline that converts harness summaries into structured telemetry training rows with quality gates and redacted manifests under `artifact-staging/results/telemetry_sim_capture/`. |
| `gen_cert.sh` | Self-signed TLS cert for the mock (the device does no cert pinning, so any cert works). |
| `ordering_attack_client.py` | State-machine-bypass ordering attack: opens fresh connections and sends `METADATA`/`FILE`/`HASH`/`UPLOAD_SAVE`/`UPLOAD_COMPLETE` before any `HELLO`, and the whole normal sequence in **reverse opcode order** with no `HELLO` at all, to test whether the server enforces any step ordering or auth prerequisite. `python3 ordering_attack_client.py --port 8443 [--out results.json]`. |
| `neg_zero_length_probe.py` | Sends the 8-byte BE length prefix as `0`, `-1`, `-2**63` (INT64_MIN / `0x8000000000000000`) and `-2**40` on `HELLO`/`METADATA`/`FILE` (distinct from the existing oversized-positive-length DoS case) to see whether a negative/zero declared length is cast to a huge unsigned size, underflows, or desyncs framing. `python3 neg_zero_length_probe.py --port 8443 [--out results.json]`. |
| `frame_desync_client.py` | Sends a **valid, positive-length** `FILE` frame (e.g. declared length 1) but appends extra bytes past that length in the *same* `sendall()`/TCP write — a well-formed short frame with a booby-trapped tail, distinct from the negative/zero-length case above. Proves (a) the trailing byte(s) get misread as a brand-new opcode (phantom-opcode injection: an operation the client never sent as a discrete frame) and (b) trailing bytes can be a fully-formed `METADATA` opcode + huge length field, which the server then blocks on forever (thread hang) because it never sent that length as a real op. `python3 frame_desync_client.py --port 8443`. |
| `adversarial_json_fuzzer.py` | Adversarial-**JSON-shape** fuzzer for the `HELLO`/`METADATA` payload specifically: duplicate JSON keys, the auth-token typed as `null`/bool/array/object/number instead of a string, 2000-level-deep nested arrays in an otherwise small frame, and raw NUL / invalid-UTF-8 bytes inside a JSON string field — with a benign-HELLO liveness check after every case. `python3 adversarial_json_fuzzer.py --port 8443 [--json-out results.json]`. |
| `hello_ack_probe.py` | Targeted probe: sends a bogus HELLO client-ack byte (instead of the expected `OK`=1, including values that collide with real opcode numbers like 4/6/12) and replays the rest of the normal upload flow, to check whether the unvalidated ack can desync the parser or get dispatched as an opcode. Usage: `python3 hello_ack_probe.py --port 8543 --ack 12`. |
| `running_hash_probe.py` | Tests whether the server's per-connection running SHA-256 (`received_file` in `handle()`) is reset between upload cycles on a reused connection: `python3 running_hash_probe.py --port 8443`. Confirmed it is **not** reset -- see verified results below. |
| `hash_framing_fuzz.py` | HASH-frame (opcode 7) boundary probe, distinct from `frame_desync_client.py`'s length-prefixed `FILE` case: HASH has no length prefix at all, just a bare fixed 32-byte read (`recvn(conn, 32)`). Sends 33 bytes (32-byte digest + 1 extra byte crafted as opcode 8/UPLOAD_SAVE) in a single write to test over-read opcode smuggling, and 31 bytes (withholding the last byte) to test under-read thread blocking. `python3 hash_framing_fuzz.py --port 8443 [--out results.json]`. Confirmed both -- see verified results below. |
| `slowloris_attack.py` | **Connection/thread-exhaustion (slowloris-style) attack**, distinct from the oversized-length allocation DoS below: opens many concurrent connections and on each sends a small, legitimate-looking `FILE` length header (e.g. 1000) then only 1 body byte, holding the socket open forever with no further data. Exploits the one-thread-per-connection model + no per-socket recv timeout + an unguarded `srv.accept()` in the main loop. `python3 slowloris_attack.py --port 8443 --connections 400 --hold 15 --canary`. Confirmed a full process crash -- see verified results below. |
| `log_injection_probe.py` | **Log-injection probe**: puts raw CRLF and ANSI/OSC escape bytes directly into the wire bytes of the HELLO `authToken` / METADATA detection fields (bypassing `json.dumps()`, which would otherwise escape them into inert text) to test whether the server's unsanitized `print()`-based logging of received payloads can be used to forge fake log lines or inject terminal-executing escape sequences. `python3 log_injection_probe.py --port 8443`. Confirmed a real log-forging bug (not a crash) -- see verified results below. |
| `crashpack_coordinate_probe.py` | Offline crash-pack coordinate scanner: recursively scans unpacked crash-log files for likely coordinate evidence (`latitude`, `longitude`, `lat=`, `lon=`, `gps`) and reports per-file hit counts + sample lines, including `ciroc` files. The scan stays within the crashpack root, ignores escape symlinks, and emits explicit read diagnostics instead of silently dropping errors. Use this to verify/refute the current GPS-in-logs contradiction with line-level evidence. `python3 crashpack_coordinate_probe.py /path/to/unpacked/crashpack [--json]`. |
| `endpoint_map_quality_gate.py` | Endpoint-host normalization quality gate for crashpack endpoint-map claims. Reads `full_crashpack_analysis.json`, computes valid-domain vs uncertain-token ratios, and fails closed when thresholds are not met. |
| `binder_camera_fuzz.py` | Bounded Binder camera probe lane with mandatory runtime preflight (service reachability + required camera socket check) so missing camera transport is explicitly reported as blocked. |
| `reaperd_wire_probe.py` | Reaperd runtime preflight/probe lane that checks `/dev/socket/reaperd` presence and optional bounded connect probe before any wire-fuzz claim. |
| `honggfuzz/` | honggfuzz upload-protocol automation: black-box replay against the Python mock plus a coverage-guided netdriver scaffold. See `tools/sandbox/honggfuzz/README.md`. |
| `honggfuzz/run_surface_routes.py` | Deterministic route wrapper for undercovered probes: `gps-log` (runs `crashpack_coordinate_probe.py`) and `protocol-control` (runs `hello_ack_probe.py` for HELLO-ack control-plane behavior). Supports `--dry-run` for command-only checks. |

### Route-expansion commands (deterministic)

```bash
python3 tools/sandbox/honggfuzz/run_surface_routes.py gps-log --dry-run
python3 tools/sandbox/honggfuzz/run_surface_routes.py protocol-control --dry-run --plaintext --port 8443 --ack 12
```

### Android-runtime preflight probes (camera/reaperd)

These classify target-mismatch blockers explicitly and exit non-zero when prerequisites are absent:

```bash
python3 tools/sandbox/binder_camera_fuzz.py --json
python3 tools/sandbox/reaperd_wire_probe.py --json
```

If the emulator image lacks vendor sockets but you still need to execute the virtualized lane:

```bash
python3 tools/sandbox/binder_camera_fuzz.py --json --virtualized-allow-missing-socket --execute
python3 tools/sandbox/reaperd_wire_probe.py --json --virtualized-allow-missing-socket
```

### Endpoint-map quality gate

Fail endpoint-map completion if normalized host quality is below threshold:

```bash
python3 tools/sandbox/endpoint_map_quality_gate.py \
  --analysis-json artifact-staging/fleetlog_real_corpus/full_crashpack_analysis.json \
  --json-out artifact-staging/results/endpoint_map_quality_gate.json
```

### Telemetry simulation capture (collector/parse modes)

```bash
python3 tools/sandbox/telemetry_sim_capture.py --mode collect
python3 tools/sandbox/telemetry_sim_capture.py --mode parse --min-rows 6
```

### Client-side fuzz harness (request/response + state transitions)

The harness stays local/emulated-only and captures whether the client tolerates malformed
server replies or continues after FAIL acks:

```bash
python3 tools/sandbox/client_fuzz_harness.py
python3 tools/sandbox/client_fuzz_harness.py --scenario metadata-fail-ack
```

Output artifacts are written to:

`tools/sandbox/campaign_results/client_harness_<timestamp>/summary.json`

Fail-ack scenarios now also emit redacted decision traces by default:

`artifact-staging/fail_ack_traces/fail-ack-<scenario>.json`

### Default validation runner

Run the default local validation bundle (harness + hardening pytest) and generate redacted summaries:

```bash
python3 tools/sandbox/validation_runner.py
```

Summary artifacts are written to:

- `artifact-staging/results/sandbox_validation_summary_redacted.json`
- `artifact-staging/results/sandbox_validation_summary_redacted.md`

The runner exits non-zero when harness mismatches or test failures are present.

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
- **`ordering_attack_client.py` confirmed the server has no state machine at all:** every ordering-violation case (METADATA/FILE/HASH/UPLOAD_SAVE/UPLOAD_COMPLETE sent on a brand-new connection with no HELLO, and the entire normal sequence sent in reverse opcode order with no HELLO) got a plain `OK` (`0x01`) back, because `handle()` dispatches on whatever opcode arrives next in a flat loop with no state variable. No opcode requires a prior HELLO/auth, SESSION, or UPLOAD_START. See `tools/sandbox/campaign_results/20260919_103513/ordering_results.json` and `tools/sandbox/campaign_results/20260919_103513/server.log`.
- **`neg_zero_length_probe.py` found a distinct desync bug, not a crash:** a negative or zero length prefix does *not* get cast to a huge unsigned size (Python's `struct.unpack(">q", ...)` keeps it a signed int, unlike a naive C `size_t` cast) and does *not* hang or crash the handler. Instead, because the read loop is `while len(buf) < n: buf += recv(...)`, a non-positive `n` makes the condition false on the first check, so the read is skipped entirely and an **empty payload is accepted as valid** for HELLO/METADATA/FILE. The bytes the client sent as that message's body are never consumed for that opcode — they sit in the stream and get **re-read one byte at a time as the next opcodes**, each triggering "unknown opcode NN — sending OK, continuing" (confirmed in the server log: the JSON body's own bytes, e.g. `"`, `a`, `u`, `t`, `h`..., appear individually as opcodes 34, 97, 117, 116... right after a negative-length HELLO). I.e. a non-positive length prefix causes a real length-check bypass / framing desync distinct from the oversized-positive-length allocation DoS. The mock server itself never crashed or hung (confirmed alive with a normal HELLO round-trip immediately after all 12 cases).
- **`frame_desync_client.py` confirmed frame desync from a *valid* short length, and escalated it to a hang:** unlike the negative/zero-length case, this uses an ordinary positive `FILE` length (1) — fully legal framing — then appends extra bytes in the same write. Server log proves desync directly: `FILE declared 1B` / `received 1B` immediately followed by `<- opcode 200 (?)` / `!! unknown opcode 200` for a byte the client never sent as its own frame, all on one connection with no error. Worse, replacing the trailing marker byte with a complete `METADATA` opcode + an 8-byte length of 2**40 makes the handler read those as a genuine new frame and block inside `recvn()` waiting for data that will never come — the connection's server thread hung (5s+, zero response) until the client closed the socket. So a single short, otherwise-unremarkable upload write can silently inject extra protocol operations or wedge a worker thread indefinitely, entirely within RFC-valid length-prefixed framing (no negative/overflow length needed).
- **`running_hash_probe.py` confirmed a running-hash non-reset bug (integrity-check logic error, not a crash/DoS):** `handle()` creates one `hashlib.sha256()` per TCP connection and never re-initializes it between SESSION/START...SAVE/COMPLETE cycles. On a reused connection, capture A's upload verifies fine (`sha256(A)` matches), but capture B's own correct `sha256(B)` is then rejected as a mismatch -- the server log shows its internal digest at that point is actually `sha256(A+B)` (confirmed byte-for-byte against the client's own computed `sha256(A+B)`). A stale/replayed HASH op with no new FILE in between also still "matches" (`digest()` is non-destructive). Net effect: the HASH check does not bind to the specific file just uploaded, it binds to everything ever sent on that connection -- so a legitimate second capture in one session spuriously fails integrity, and (in principle) any client that tracks the server's running state could satisfy the check without the declared per-capture hash actually describing that capture. The server itself never crashed or hung; it just kept returning `FAIL(0)` for the correct per-file hash.
- **`hash_framing_fuzz.py` confirmed HASH (opcode 7) is the one op with no length prefix and no terminator — just a bare fixed 32-byte read — and that boundary is exploitable both ways:**
  - **Over-read → opcode smuggling (confirmed):** sending 33 bytes in one `sendall` after the HASH opcode byte (correct 32-byte digest + one extra byte set to `8`/UPLOAD_SAVE) makes `recvn(conn, 32)` correctly stop at 32 bytes for the hash compare, but the 33rd byte is left sitting in the socket's receive buffer. The very next loop iteration's `conn.recv(1)` (meant to read the next opcode the client explicitly sends) picks it up instead: the server log shows a bare `<- opcode 8 (UPLOAD_SAVE)` line the client never sent as its own frame, and the client observes **2** response bytes (`[1, 1]`) after sending only one logical HASH request with no further writes. Opcode 8 here is a no-op ack, so this run's impact is "unsolicited state transition smuggled in," not corruption — but it demonstrates the general class: any opcode with a real side effect could be smuggled the same way by controlling a trailing byte after a HASH frame.
  - **Under-read → per-connection hang (confirmed):** sending only 31 of the 32 digest bytes and withholding the last one blocks the handler thread inside `recvn`'s `conn.recv()` indefinitely (no response for 4s+, vs. the baseline case which never stalls) — the read has no timeout. Sending the missing byte later lets the same connection resume normally, proving it was a genuine blocking wait, not a crash. Since `upload_server.py` is one-thread-per-connection this is a cheap per-connection resource hold (slow-loris-style) against this specific opcode, not a full-server crash. See `tools/sandbox/campaign_results/20260919_103513/server.log` and `tools/sandbox/campaign_results/20260919_103458/server.log`.
- **`adversarial_json_fuzzer.py` — the 16-case JSON-shape battery was fully benign:** duplicate `authToken` keys, `authToken` typed as `null`/`true`/an array/an object/a number, a missing `authToken` field, 2000-level-deep nested arrays (as a HELLO field value, as a METADATA field value, and as a bare top-level payload with no object wrapper), a raw NUL byte inside a string field, and three invalid-UTF-8 byte sequences inside a string field — all 16 got a normal `{"status":"ok","mock":true}` HELLO reply (or `OK` ack for METADATA), and a benign HELLO immediately after each case still round-tripped correctly (0 timeouts, 0 exceptions, 0 post-case health-check failures). Root cause confirmed from the server log: `handle()` never actually parses the HELLO/METADATA payload as JSON at all — it only does `payload.decode("utf-8", "replace")` and logs the first 400 characters — so none of these JSON-shape attacks (duplicate keys, wrong-typed token, deep nesting) reach any recursive-descent parser or key/type-dispatch logic in the mock; invalid UTF-8 is silently replaced with U+FFFD and a raw NUL simply survives as a character in the Python string. This means the mock (as reversed from `ConnectionClient`'s server-facing wire behavior) cannot exercise whatever *actual* JSON parser the real device/backend uses on this field — it only proves the transport/framing layer tolerates arbitrary payload bytes of this shape. See `tools/sandbox/campaign_results/20260919_103513/server.log`.
- **`slowloris_attack.py` confirmed a full server crash from connection-count exhaustion, a distinct bug class from the oversized-length allocation DoS:** never declaring an oversized length (FILE length=1000, well within normal bounds), just opening many connections and sending 1 body byte then stalling forever. With the server's file-descriptor limit constrained to 200 (to make the threshold reachable quickly/reproducibly -- the code path is unconditional at any ulimit), 194 concurrently-stalled connections were enough to exhaust it: `srv.accept()` in the main loop raised `OSError: [Errno 24] Too many open files`, which is **not caught** (the loop only catches `KeyboardInterrupt`), so the exception propagated out of `main()` and killed the entire server process. A legitimate canary upload attempted during the hold got `ConnectionRefusedError` -- no listener was left at all, not just the attacker's own connections starved. Root cause: unbounded one-thread-per-connection accept loop, no `socket.settimeout()` on accepted connections, and no exception handling around `accept()` beyond Ctrl-C. See `tools/sandbox/campaign_results/20260919_103513/slowloris_attack.log` and `tools/sandbox/campaign_results/20260919_103513/server.log`.
- **`log_injection_probe.py` confirmed a real log-forging bug, not a crash:** `handle()` never parses HELLO/METADATA as JSON — it only UTF-8-decodes the raw bytes and `print()`s a slice — so a string field containing a genuine (not `json.dumps()`-escaped) `\r\n` produces **two newline-separated lines in the server's log from one `print()` call**, and the injected second line can be crafted to exactly match the server's own `f"[{addr[1]}] ..."` prefix format with a fake connection id, making it indistinguishable by format from a real log record (`grep -n '^\[9999\]' server_raw.log` matches it). The same technique forged a fake "file received, sha256=..." completion line inside a METADATA detection field even though no FILE frame was sent. Raw ANSI CSI (cursor-up/clear-line) and OSC-0 (set-terminal-title) escape bytes also pass straight through, which would execute on a real terminal tailing the log (`tail -f`), capable of overwriting/hiding the previous real line. Building the same payloads with `json.dumps()` instead (the spec-conforming way) is a **no-op** — it escapes `\r`/`\n`/`\x1b` into literal backslash text first — so this only fires when the raw wire bytes carry an actual unescaped control byte. No crash/hang: the server kept responding normally throughout and after. See `tools/sandbox/campaign_results/20260919_103513/server.log`.

## Emulator + Frida (provided; correction below — `/dev/kvm` is NOT actually required)
**Correction**: this section originally assumed a hardware-accelerated (`/dev/kvm`) host was
required and that these scripts were only "syntax-checked, not run." That assumption is
wrong — `tools/jni-harness/README.md`'s validated setup got a real, genuinely-ARM Android guest
fully booted and `adb`-connected on this exact WSL2 box with no `/dev/kvm` at all (by
invoking the SDK's arch-specific `qemu-system-armel-headless` binary directly instead of the
`emulator` launcher, which imposes an unrelated architecture restriction of its own), and
got the real, unmodified `flock-object` app executing real code on it. See that README for
the full recipe (system image, signing-key, and dex-version fixes needed) before assuming
this leg needs different hardware — it doesn't, it's just slower (TCG, no acceleration).
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
