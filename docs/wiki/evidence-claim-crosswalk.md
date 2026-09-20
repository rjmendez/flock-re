# Evidence-claim crosswalk: non-Android findings

**Purpose**: Precise mapping from each claim statement to exact artifact files, wiki sources, and confidence levels.

**Methodology**: Read-only analysis; claims extracted from wiki with line references; evidence graded conservatively; no-proof markers applied explicitly.

**Date**: 2026-09-19

---

## Claim-to-artifact table

| # | Claim | Wiki source (file:line) | Claim text | Artifact file(s) | Confidence | Caveat/gap |
|---|---|---|---|---|---|---|
| 1 | Ordering/state bypass — mock accepts operations out of order including pre-HELLO | `non-android-fuzz-findings.md:8-9` | "The mock accepts protocol operations out of order, including pre-HELLO sequences." | `campaign_results/20260919_103513/ordering_results.json` (JSON: 8+ cases) + `ordering_attack.log` + `server.log` | **HIGH** (0.95) | Claims tested on mock only; real backend ordering enforcement unknown |
| 2 | Ordering/state bypass — full reverse sequence accepted | `non-android-fuzz-findings.md:8-9` (implied via exploitability table line 20) | [Implicit from "Ordering/state bypass" class and test script evidence] | `campaign_results/20260919_103513/ordering_results.json` (case: "FULL_SEQUENCE_REVERSE_ORDER_no_HELLO") | **HIGH** (0.93) | **NO PROOF** that reverse order causes any real-backend fault; may be spec-compliant if auth/state-gating is real backend's responsibility |
| 3 | Length-prefix desynchronization — non-positive lengths desynchronize frame consumption | `non-android-fuzz-findings.md:11-12` | "Non-positive declared lengths can desynchronize frame consumption and opcode parsing." | `neg_zero_length_probe.py` (source code), `server.log` (bytes reinterpreted as opcodes: e.g., `"`, `a`, `u`, `t`, `h` as 34, 97, 117, 116) | **HIGH** (0.92) | Proof of mock behavior only; real C/Rust parser may handle signed/unsigned ints differently |
| 4 | HASH frame over-read — 33-byte payload causes opcode smuggling | `non-android-fuzz-findings.md:14-15` (and exploitability table line 19) | "Over-read smuggling and under-read holds are reproducible at the fixed 32-byte HASH boundary." | `hash_framing_fuzz.py` (source), `server.log` (opcode 8 phantom line: `<- opcode 8 (UPLOAD_SAVE)` never sent by client) | **HIGH** (0.93) | Boundary condition verified; real backend may have guard checks |
| 5 | HASH frame under-read — 31-byte payload causes indefinite block | `non-android-fuzz-findings.md:14-15` (and exploitability table line 19) | [Implicit via "Over-read smuggling and under-read holds"] | `hash_framing_fuzz.py` (source), `server.log` (stall time >4s) | **HIGH** (0.90) | Timing-dependent; real backend may enforce recv() timeout |
| 6 | Valid-short-frame tail injection — valid short frame + extra bytes injects behavior | `non-android-fuzz-findings.md:17-18` | "A valid short FILE frame with appended bytes can inject follow-on protocol behavior." | `frame_desync_client.py` (source), `server.log` (phantom opcode 200 + thread hang) | **HIGH** (0.94) | Escalation to thread hang tested; real backend may have frame-resync recovery |
| 7 | Connection-exhaustion susceptibility — many stalled connections degrade/terminate service | `non-android-fuzz-findings.md:20-21` (and exploitability table line 22) | "Many stalled connections can degrade or terminate mock service availability." | `slowloris_attack.py` (source), `slowloris_attack.log` (50 connections opened, held 20s, probes succeeded), `server.log` (full crash at 194 connections) | **HIGH** (0.88) | Production arch unknown; real backend likely has connection pools/worker limits/timeouts |
| 8 | HELLO continuation-byte acceptance — non-OK values accepted | `non-android-fuzz-findings.md:23-24` | "Non-OK continuation-byte values are accepted in the mock." | `hello_ack_probe.py` (source: tests ack values 0, 4, 12, 255), `hello_ack_probe_ack0/4/12/255.log` (all succeed) | **HIGH** (0.91) | Mock has no validation; real backend may reject invalid ack bytes |
| 9 | Log control-byte injection — unsanitized control bytes forge/alter log output | `non-android-fuzz-findings.md:26-27` | "Unsanitized control bytes can forge/alter mock log output formatting." | `log_injection_probe.py` (source: CRLF, ANSI CSI, OSC-0), `server.log` (forged lines with exact `[port]` prefix match, escape sequences passed through) | **HIGH** (0.89) | Production logging architecture unknown; likely sanitizes output |
| 10 | Running-hash non-reset — hash state persists across upload cycles | `sandbox/README.md:~365-370` (implicit in verified results section) | "handle() creates one hashlib.sha256() per TCP connection and never re-initializes it between SESSION/START...SAVE/COMPLETE cycles" | `running_hash_probe.py` (source), server hash computed as sha256(A+B) on second upload, `server.log` | **HIGH** (0.92) | Integrity-check bypass demonstrated on mock; real backend may reset per-session |
| 11 | JSON payload parsing — adversarial shapes are benign | `sandbox/README.md:~285-300` (documented in fuzzer description) | [Implicit: "adversarial_json_fuzzer.py — the 16-case JSON-shape battery was fully benign"] | `adversarial_json_fuzzer.py` (source: 16 cases), `server.log` (all cases: status=ok responses) | **MODERATE** (0.70) | **CAVEAT: Mock does not parse JSON** — only UTF-8-decodes and logs first 400 chars. Proves transport robustness, not parser hardness. Real backend parser likely rejects many of these. |
| 12 | Protocol version enforcement — version-3 marker (opcode 3) behavior | `backend-protocol.md` (implied in opcode table) | [Implicit: version marker exists; enforcement unknown] | **NO ARTIFACT** | **NONE** (0.0) | **NO-PROOF**: Opcode 3 reversed from decompiled code; enforcement behavior on mock/real never tested |

---

## Explicit "no-proof" markers

These claims appear in wiki documentation or are implied by findings but **lack direct artifact evidence**:

| Claim | Wiki source | Why no proof | Suggested evidence |
|---|---|---|---|
| Real backend enforces opcode ordering | `non-android-fuzz-transfer-validation.md:10` (success criterion: "Invalid order rejected/state-gated") | Mock accepts all orderings; real backend behavior unknown | Execute ordering probe against authorized real endpoint |
| Real backend rejects non-positive lengths | `non-android-fuzz-transfer-validation.md:11` (success criterion: "Malformed frame rejected") | Mock accepts zero/negative lengths silently; real C behavior unknown | Fuzz real parser with length-prefix attacks |
| Real backend enforces connection timeouts | `non-android-fuzz-repro.md:~25-30` (expected signals: "Timeout/abort enforced") | Mock has no timeouts; HASH under-read stalls forever | Monitor real backend socket behavior under load |
| Real backend has rate limiting | `backend-protocol.md` (implied by device auth) | No test probe exists; mock server has no rate limit | Design rate-limit probe (>N requests/time window) |
| Real backend recovers from frame desync | `sandbox/README.md` (frame-desync section) | No frame-resync test exists on mock | Send malformed frame, then valid frame; measure recovery |
| Production log output is sanitized | `non-android-fuzz-findings.md:26-27` (claim: "unsanitized control bytes") | Mock log injection succeeds; production logging unknown | Inspect real backend log handling (requires access) |
| HASH frame has no length prefix (real backend) | `backend-protocol.md` + `sandbox/README.md` (opcode table: "HASH: 32-byte SHA-256") | Reversed from decompiled client code only; never tested against real backend wire format | Capture real device → backend communication |
| Running hash is reset per-session (real backend) | `sandbox/README.md` (implied as bug only on mock) | Mock confirmed non-reset; real backend behavior unknown | Test reused connection on real backend |
| Continuation-byte field must be OK (0x01) (real backend) | Implied by protocol spec; not documented as tested | Mock accepts any value; real backend validation unknown | Fuzz real backend with invalid ack values |
| Opcode 3 (version marker) enforcement | `backend-protocol.md` (opcode table) | Marker reversed from code; no test of enforcement on mock or real backend | Send mismatched protocol versions to mock/real |

---

## Confidence grading scale

| Score | Range | Meaning |
|---|---|---|
| **HIGH** | 0.88–0.95 | Direct artifact evidence on mock; finding class documented in detail; test script reproduces consistently; logs confirm behavior |
| **MODERATE** | 0.60–0.87 | Related evidence exists; caveat or condition applies; or mock omits key code path (e.g., JSON parsing) |
| **LOW** | 0.30–0.59 | Indirect evidence; inferred from code review; or artifact exists but testing incomplete |
| **NONE** | 0.0–0.29 | No artifact; claim inferred only from decompiled code or documentation; untested behavior |

---

## Claim categories by proof status

### ✅ Strong evidence (HIGH confidence, 0.88–0.95)

- Ordering/state bypass (0.95)
- Ordering full-reverse sequence (0.93)
- Length-prefix desync (0.92)
- HASH over-read smuggling (0.93)
- HASH under-read hold (0.90)
- Valid-short-frame tail injection (0.94)
- Connection exhaustion (0.88)
- HELLO continuation-byte acceptance (0.91)
- Log control-byte injection (0.89)
- Running-hash non-reset (0.92)

**Total: 10 claims**, all mock-confirmed, all highly reproducible.

### ⚠️ Moderate evidence (0.60–0.87)

- JSON payload shape tolerance (0.70)

**Caveat**: Mock does not parse JSON; only tests transport robustness. Real backend parser behavior unknown.

**Total: 1 claim**, with explicit caveat.

### ❌ No proof (0.0–0.29)

- Protocol version enforcement (0.0) — opcode 3 existence reversed from code; enforcement never tested
- Real backend ordering enforcement (assumed NO-PROOF without real-backend test)
- Real backend length validation (assumed NO-PROOF without real-backend test)
- Real backend timeouts (assumed NO-PROOF; mock has none)
- Real backend rate limiting (assumed NO-PROOF; never probed)
- Real backend log sanitization (assumed NO-PROOF; mock injection succeeds)

**Total: 6+ implicit no-proof claims** (wiki documents real-backend transfer criteria but does not claim current proof of real-backend behavior).

---

## Artifact inventory by finding class

| Finding class | JSON evidence | Log evidence | Source code evidence | Count |
|---|---|---|---|---|
| **Ordering/state bypass** | ordering_results.json (8+ cases) | ordering_attack.log, server.log | ordering_attack_client.py | 2 files + code |
| **Length-prefix desync** | (none) | server.log (reinterpreted bytes) | neg_zero_length_probe.py | 1 file + code |
| **HASH over-read** | (none) | server.log (phantom opcode 8) | hash_framing_fuzz.py | 1 file + code |
| **HASH under-read** | (none) | server.log (stall evidence) | hash_framing_fuzz.py | 1 file + code |
| **Valid-short-frame tail** | (none) | server.log (opcode 200, thread hang) | frame_desync_client.py | 1 file + code |
| **Connection exhaustion** | (none) | slowloris_attack.log, server.log (crash) | slowloris_attack.py | 2 files + code |
| **HELLO ack acceptance** | (none) | 4× hello_ack_probe_ack*.log (all succeed) | hello_ack_probe.py | 4 files + code |
| **Log injection** | (none) | server.log (forged lines, escapes) | log_injection_probe.py | 1 file + code |
| **Running-hash** | (none) | server.log (hash mismatch) | running_hash_probe.py | 1 file + code |
| **JSON shapes** | (none) | server.log (benign responses) | adversarial_json_fuzzer.py | 1 file + code |

**Summary**: 11 finding classes; 9 strong (HIGH confidence); 1 moderate (caveat on JSON); 1 none (protocol version). Total: 12 log files + 11 test scripts.

---

## Top 5 highest-impact evidence gaps to collect next

| Rank | Gap | Impact | Why missing | Collection effort | Transfer value |
|---|---|---|---|---|---|
| **1** | **Real backend ordering enforcement** | Blocks transfer of ordering/state-bypass findings | Mock accepts all orderings; real backend auth/gating unknown | HIGH (requires authorized endpoint) | CRITICAL — ordering bypass is HIGH severity (8/10 exploitability) |
| **2** | **Real backend length-prefix validation** | Blocks transfer of length-desync findings | Mock accepts zero/negative lengths; real C parser behavior unknown | HIGH (fuzz real parser) | CRITICAL — length-desync is HIGH severity (7/10) |
| **3** | **Real backend frame-error recovery** | Blocks transfer of valid-short-frame and HASH-boundary findings | No frame-resync probe exists; escalation to thread hang only on mock | MEDIUM (<10 min probe design) | HIGH — would clarify if real backend can recover from malformed frames |
| **4** | **Real backend connection timeout enforcement** | Blocks transfer of HASH under-read and connection-exhaustion findings | Mock has no timeouts; HASH stalls indefinitely; slowloris crashes server | HIGH (monitor real backend under load) | HIGH — timeouts are primary DoS mitigation |
| **5** | **Real backend receipt/rejection of invalid continuation-byte** | Blocks transfer of HELLO ack findings | Mock accepts ack values 0, 4, 12, 255; real backend validation unknown | MEDIUM (replay real backend with invalid ack) | MEDIUM — ack is medium severity (6/10) but simple to transfer-test |

**P0 candidates** (must collect before claiming transfer success): Gaps 1, 2, 4  
**P1 candidates** (high-value if collected): Gaps 3, 5

---

## Summary statistics

| Metric | Count |
|---|---|
| **Total unique claims** | 12 |
| **Claims with HIGH confidence (0.88+)** | 10 |
| **Claims with MODERATE confidence (0.60–0.87)** | 1 |
| **Claims with NO proof (0.0–0.29)** | 1 |
| **Mock-confirmed findings** | 10 |
| **Real-backend verified findings** | 0 |
| **Transfer-tested findings** | 0 |
| **Artifact files (logs + JSON)** | 12 |
| **Test scripts (reproducers)** | 11 |
| **Wiki source pages referenced** | 5 |
| **Line references extracted** | 20+ |

---

## References & cross-links

**Primary wiki sources**:
- `docs/wiki/non-android-fuzz-findings.md` — claim definitions (lines 8–27)
- `docs/wiki/non-android-fuzz-repro.md` — reproducibility specs
- `docs/wiki/non-android-fuzz-transfer-validation.md` — real-backend transfer matrix
- `docs/wiki/backend-protocol.md` — protocol shape (opcode table)
- `tools/sandbox/README.md` — verified results section (~365–500 lines)

**Artifacts**:
- `tools/sandbox/campaign_results/20260919_103513/` (primary campaign)
- `tools/sandbox/campaign_results/20260919_103458/` (secondary)
- `tools/sandbox/*.py` (11 test scripts)

**Related indexes**:
- `docs/wiki/artifact-proof-index.md` — proof coverage by finding class
- `docs/wiki/claims-vs-evidence.md` — Android firmware claims validation

---

## Revision history

| Date | Change |
|---|---|
| 2026-09-19 | Initial crosswalk; 12 claims catalogued; 10 HIGH + 1 MODERATE + 1 NONE; 5 evidence gaps prioritized |
