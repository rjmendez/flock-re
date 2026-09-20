# Claim versioning and annotation specification

Security research framework for tracking claim supersessions, amendments, retractions, and confidence changes across analysis waves.

**Purpose**: Enable auditable claim history so research remains current and falsifications are explicit without loss of trail.

---

## SECTION A: Canonical version annotation model

**Core data structure for each claim revision:**

| Field | Type | Required | Example | Notes |
|---|---|---|---|---|
| claim_id | string | YES | `ORDERING_BYPASS_001` | Immutable identifier; prefix is finding class (all revisions share) |
| revision_id | string | YES | `ORDERING_BYPASS_001.r2` | Append `.r{N}` for revision count; r1 = initial |
| prior_revision | string | NO | `ORDERING_BYPASS_001.r1` | NULL for initial; links to previous revision record |
| change_type | enum | YES | `correction`, `confidence-downgrade` | See taxonomy section below |
| effective_cycle | integer | YES | `1` | Wave number when revision was issued (1=initial, 2+=post-transfer-validation) |
| status | enum | YES | `RETAINED`, `DOWNGRADED`, `SUPPRESSED`, `FALSIFIED` | Publication disposition per disagreement matrix |
| confidence_prior | float | NO | `0.90` | Confidence score of prior revision (anchoring change magnitude) |
| confidence_current | float | YES | `0.75` | Confidence score effective with this revision |
| rationale | text | YES | `Real backend accepts HELLO before SESSION, contradicting mock behavior` | Concise justification for change |
| evidence_delta | text | NO | `Added: endpoint_logs/20260920_run5.log lines 234-240` | What new evidence triggered change |
| caveat_added | text | NO | `Ordering may be application-layer constraint, not protocol-layer` | Qualification strengthened by this revision |
| line_ref_updated | text | NO | `docs/wiki/non-android-fuzz-findings.md line 12` | Where claim text was modified |
| integrity_check | string | YES | `PASS` | PASS/AUDIT_REQUIRED; see validation rules |
| timestamp_issued | string | YES | `2026-09-20T14:32:15Z` | ISO 8601 UTC of publication |
| author_id | string | YES | `security_cycle_1_ops` | Operator/wave that issued revision |

---

## SECTION B: Change-type taxonomy

Seven canonical change types capturing all claim mutations:

| Change type | When applied | Confidence effect | Status allowed | Example rationale |
|---|---|---|---|---|
| **initial** | Initial cycle, finding is published | — | RETAINED | Claim originates; cycle 1 discovery |
| **correction** | Factual error in prior phrasing (not evidence-driven) | No change | RETAINED | Mock vs real server log quote was misinterpreted; phrasing corrected |
| **caveat-strengthening** | Add qualification without changing confidence | No change | RETAINED | Add: "ordering may be app-layer; protocol layer unknown" |
| **confidence-upgrade** | New evidence supports stronger claim | +0.05 to +0.20 | RETAINED | Negative control NC3 passed; real backend exhibits same behavior |
| **confidence-downgrade** | Evidence gap or fidelity gap surfaces | –0.10 to –0.40 | DOWNGRADED | Negative control NC7 failed; mock behavior may not transfer |
| **retraction** | Claim is false or unsupportable on real backend | –1.0 | FALSIFIED | Real-endpoint transfer shows opposite behavior; mock-only bug confirmed |
| **superseded** | Claim is replaced by narrower/refined version | Varies | SUPPRESSED | Split into two findings with independent evidence paths |

---

## SECTION C: Consistency rules linking version annotations to evidence, status, and confidence

**Rule 1: Claim ID immutability**
- `claim_id` prefix never changes across all revisions of a finding
- All revisions of ORDERING_BYPASS_001 retain prefix `ORDERING_BYPASS_001`
- Example chain: `ORDERING_BYPASS_001.r1` → `.r2` → `.r3`

**Rule 2: Prior-revision linkage**
- Every revision with `prior_revision` != NULL must link to a published revision record
- Creates auditable chain: r1 ← r2 ← r3
- Enables "show history" and "compare to prior" queries

**Rule 3: Change-type vs. status consistency**
- `correction` and `caveat-strengthening` → status MUST be RETAINED (no disposition change)
- `confidence-upgrade` → status MUST be RETAINED
- `confidence-downgrade` → status MUST be DOWNGRADED or RETAINED (confidence drop alone doesn't suppress)
- `retraction` → status MUST be FALSIFIED
- `superseded` → status MUST be SUPPRESSED

**Rule 4: Confidence monotonicity per status**
- RETAINED: confidence may increase (upgrade) or decrease slightly (technical caveat)
- DOWNGRADED: confidence must drop ≥0.10 from prior; ≥0.15 typical
- SUPPRESSED: confidence becomes 0.0; claim not published in main findings table
- FALSIFIED: confidence becomes 0.0; moved to "Mock-only bugs" section with explicit contradiction evidence

**Rule 5: Revision-cycle sequencing**
- `effective_cycle` is monotonically non-decreasing across revision chain
- Cycle 1 = initial publication; Cycle 2+ = post-transfer-validation updates only
- No back-dating revisions to prior revision cycles

**Rule 6: Evidence delta must anchor confidence changes**
- If `change_type` is `confidence-upgrade` or `confidence-downgrade`, `evidence_delta` MUST cite new artifact
- Bare confidence change without evidence_delta → integrity_check = AUDIT_REQUIRED
- Format: `Added: {file_path} lines {start}–{end}` or `Removed: {file_path} (fidelity gap)` or `Negative control {NC_id} failed`

**Rule 7: Status/confidence cap per disagreement disposition**
- RETAIN: confidence cap = 1.0 (no change)
- DOWNGRADE: confidence cap = 0.75
- SUPPRESS: confidence cap = 0.0 (not published)
- FALSIFIED: confidence cap = 0.0 (moved to retracted section)

**Rule 8: Caveat accumulation**
- `caveat_added` is appended to prior caveats; never replaces prior caveats
- Final caveat_text in publication combines all version caveats in chronological order
- Example: v1 caveat="mock-only" + v2 caveat="ordering may be app-layer" → final="mock-only; ordering may be app-layer"

**Rule 9: Line-ref consistency with finding docs**
- Every version with status change MUST update `line_ref_updated` to point to modified line in wiki findings file
- Enable traceability: "version r3 changed at finding line 45"
- If claim text is moved or reformatted, update line ref accordingly

**Rule 10: Integrity checks**
- PASS: all evidence_delta refs exist, confidence change is consistent with change_type, line_ref_updated points to actual update
- AUDIT_REQUIRED: confidence change without new evidence, or orphaned evidence_delta file, or line_ref mismatch
- Integrity must be PASS before publication

---

## SECTION D: Publication rules for presenting current vs. historical claim state without overclaiming

**Rule D1: "Current state" view (findings table, summary)**
- Show ONLY latest revision per claim_id (highest revision_id)
- Display: claim_id, claim_text, status (enum), confidence_current, summary_of_all_caveats
- Do NOT show revision_id, prior_revision, history chain in main table

**Rule D2: "Historical state" view (appendix or expanded claim detail)**
- Include full version_annotation records (all fields) for all revisions of claim
- Sorted by effective_cycle ascending, then revision_id ascending
- Enable readers to see evolution: "originally HIGH confidence, downgraded in cycle 2"
- Show change_type, rationale, evidence_delta, timestamp_issued

**Rule D3: Status presentation mapping**
| Status | Main table publication | Placement |
|---|---|---|
| RETAINED | Yes | "Confirmed findings" section with current confidence |
| DOWNGRADED | Yes | "Confirmed findings" with caveat banner + downgraded confidence range |
| SUPPRESSED | No | "Limitations" or "Superseded findings" appendix with reasoning |
| FALSIFIED | No | "False findings" or "Mock-only bugs" appendix with contradiction evidence |

**Rule D4: Confidence presentation**
- Round to nearest 0.05 in main table (e.g., 0.88 not 0.876)
- Show range for DOWNGRADED status (e.g., "HIGH 0.80–0.88" with notation "prior 0.92")
- Never show confidence > 0.95 without "HIGH" qualifier and explicit "verified-on-real-endpoint" marker
- Unpublished findings (SUPPRESSED/FALSIFIED) show "0.0" with link to reasoning

**Rule D5: Caveat presentation**
- List all caveats in order of version issuance
- Preface with cycle number: "[Cycle 1] mock-only; [Cycle 2] ordering may be application-layer"
- Use bold or callout box for DOWNGRADED status caveats

**Rule D6: Overclaim guards**
- No claim shall be published with status RETAINED and confidence > 0.90 unless "verified-on-real-endpoint" is explicitly in its caveat_text
- No claim shall be published with confidence > 0.80 if evidence is mock-only without caveat "unverified on real backend"
- Check: every RETAINED claim with confidence > 0.85 has transfer-validation evidence in evidence_delta or prior-version record

**Rule D7: Retraction transparency**
- Retracted claims (FALSIFIED) must be published in full in appendix with:
  - Original claim text (version r1)
  - Retraction rationale and evidence
  - Timestamp and author of retraction
  - Link to new contradictory evidence
  - Example: "Originally ORDERING_BYPASS_001.r1 claimed protocol rejects pre-SESSION opcodes. Real-endpoint testing (endpoint_logs/20260920_run5.log lines 234–240) shows HELLO before SESSION is accepted and processed normally. Retraction issued cycle 2."

**Rule D8: Cross-reference integrity**
- Every published claim must cite its latest version_annotation record (implicit link)
- Appendix version history must link back to main-table claim_id
- JSON/machine-readable export must include revision_id as identifier (not just claim_id)

---

## SECTION E: Example version-annotation records for 6 current non-Android claims

**Example 1: ORDERING_BYPASS_001 (initial → confidence-upgrade)**

```json
{
  "claim_id": "ORDERING_BYPASS_001",
  "revision_id": "ORDERING_BYPASS_001.r1",
  "prior_revision": null,
  "change_type": "initial",
  "effective_cycle": 1,
  "status": "RETAINED",
  "confidence_prior": null,
  "confidence_current": 0.90,
  "rationale": "Mock accepts HELLO, SESSION, UPLOAD_START out of order; reproducible on demand",
  "evidence_delta": null,
  "caveat_added": "Unverified on real backend; ordering may be application-layer responsibility",
  "line_ref_updated": "docs/wiki/non-android-fuzz-findings.md line 12",
  "integrity_check": "PASS",
  "timestamp_issued": "2026-09-19T10:45:22Z",
  "author_id": "security_cycle_1_ops"
}
```

Subsequent revision:

```json
{
  "claim_id": "ORDERING_BYPASS_001",
  "revision_id": "ORDERING_BYPASS_001.r2",
  "prior_revision": "ORDERING_BYPASS_001.r1",
  "change_type": "confidence-upgrade",
  "effective_cycle": 2,
  "status": "RETAINED",
  "confidence_prior": 0.90,
  "confidence_current": 0.93,
  "rationale": "Negative control NC2 (enforced ordering) passed on real endpoint; real backend shows same tolerance",
  "evidence_delta": "Added: endpoint_logs/20260920_run5.log lines 234–240; Passed: NC2_enforced_ordering",
  "caveat_added": "Real backend exhibits same ordering bypass; application-layer safeguards unknown",
  "line_ref_updated": "docs/wiki/non-android-fuzz-findings.md line 12",
  "integrity_check": "PASS",
  "timestamp_issued": "2026-09-20T14:32:15Z",
  "author_id": "security_wave_2_ops"
}
```

---

**Example 2: LENGTH_DESYNC_001 (initial → confidence-downgrade)**

```json
{
  "claim_id": "LENGTH_DESYNC_001",
  "revision_id": "LENGTH_DESYNC_001.r1",
  "prior_revision": null,
  "change_type": "initial",
  "effective_cycle": 1,
  "status": "RETAINED",
  "confidence_prior": null,
  "confidence_current": 0.88,
  "rationale": "Non-positive declared lengths desynchronize frame consumption; 6 deterministic test cases in ordering_results.json",
  "evidence_delta": null,
  "caveat_added": "Mock-only fidelity gap: mock is single-threaded with no timeout enforcement",
  "line_ref_updated": "docs/wiki/non-android-fuzz-findings.md line 18",
  "integrity_check": "PASS",
  "timestamp_issued": "2026-09-19T10:45:22Z",
  "author_id": "security_cycle_1_ops"
}
```

Downgrade revision:

```json
{
  "claim_id": "LENGTH_DESYNC_001",
  "revision_id": "LENGTH_DESYNC_001.r2",
  "prior_revision": "LENGTH_DESYNC_001.r1",
  "change_type": "confidence-downgrade",
  "effective_cycle": 2,
  "status": "DOWNGRADED",
  "confidence_prior": 0.88,
  "confidence_current": 0.72,
  "rationale": "Negative control NC5 (frame resynchronization recovery) failed on real endpoint; real backend may not exhibit desync",
  "evidence_delta": "Failed: NC5_resync_recovery; Added: endpoint_logs/20260920_run7.log lines 456–478",
  "caveat_added": "Real backend may enforce frame boundary constraints; mock desync may be mock-only fidelity gap",
  "line_ref_updated": "docs/wiki/non-android-fuzz-findings.md line 18",
  "integrity_check": "PASS",
  "timestamp_issued": "2026-09-20T16:45:33Z",
  "author_id": "security_wave_2_ops"
}
```

---

**Example 3: HASH_OVER_READ_001 (initial → retraction)**

```json
{
  "claim_id": "HASH_OVER_READ_001",
  "revision_id": "HASH_OVER_READ_001.r1",
  "prior_revision": null,
  "change_type": "initial",
  "effective_cycle": 1,
  "status": "RETAINED",
  "confidence_prior": null,
  "confidence_current": 0.85,
  "rationale": "32-byte HASH frame boundary allows over-read smuggling of up to 4 extra bytes; reproducible in hash_framing_fuzz.py lines 120–145",
  "evidence_delta": null,
  "caveat_added": "Mock-only behavior; real backend hash state reset unknown",
  "line_ref_updated": "docs/wiki/non-android-fuzz-findings.md line 25",
  "integrity_check": "PASS",
  "timestamp_issued": "2026-09-19T10:45:22Z",
  "author_id": "security_cycle_1_ops"
}
```

Retraction revision:

```json
{
  "claim_id": "HASH_OVER_READ_001",
  "revision_id": "HASH_OVER_READ_001.r2",
  "prior_revision": "HASH_OVER_READ_001.r1",
  "change_type": "retraction",
  "effective_cycle": 2,
  "status": "FALSIFIED",
  "confidence_prior": 0.85,
  "confidence_current": 0.0,
  "rationale": "Real-endpoint testing shows no over-read; behavior is mock-only due to mock's connection-agnostic frame handling. Real backend enforces strict frame boundaries per upload session.",
  "evidence_delta": "Added: endpoint_logs/20260920_run3.log lines 100–110 (over-read attempt rejected); source: ConnectionHandler.java lines 234–240",
  "caveat_added": "Mock-only fidelity gap. Real backend enforces per-upload frame state.",
  "line_ref_updated": "docs/wiki/non-android-fuzz-findings.md line 25",
  "integrity_check": "PASS",
  "timestamp_issued": "2026-09-20T09:22:11Z",
  "author_id": "security_wave_2_ops"
}
```

---

**Example 4: TAIL_INJECTION_001 (initial → caveat-strengthening)**

```json
{
  "claim_id": "TAIL_INJECTION_001",
  "revision_id": "TAIL_INJECTION_001.r1",
  "prior_revision": null,
  "change_type": "initial",
  "effective_cycle": 1,
  "status": "RETAINED",
  "confidence_prior": null,
  "confidence_current": 0.92,
  "rationale": "Valid short FILE frame with appended bytes can inject follow-on protocol behavior; 8 test cases in frame_desync_client.py lines 156–203",
  "evidence_delta": null,
  "caveat_added": "Unverified on real backend",
  "line_ref_updated": "docs/wiki/non-android-fuzz-findings.md line 32",
  "integrity_check": "PASS",
  "timestamp_issued": "2026-09-19T10:45:22Z",
  "author_id": "security_cycle_1_ops"
}
```

Caveat-strengthening revision:

```json
{
  "claim_id": "TAIL_INJECTION_001",
  "revision_id": "TAIL_INJECTION_001.r2",
  "prior_revision": "TAIL_INJECTION_001.r1",
  "change_type": "caveat-strengthening",
  "effective_cycle": 2,
  "status": "RETAINED",
  "confidence_prior": 0.92,
  "confidence_current": 0.92,
  "rationale": "No confidence change; clarify that tail injection may require frame-length desync as precondition",
  "evidence_delta": "Analyzed: frame_desync_client.py lines 156–203; Linked to: LENGTH_DESYNC_001",
  "caveat_added": "Tail injection reproducible in isolation; in-the-wild exploitability requires length-desync precondition (LENGTH_DESYNC_001)",
  "line_ref_updated": "docs/wiki/non-android-fuzz-findings.md line 32",
  "integrity_check": "PASS",
  "timestamp_issued": "2026-09-20T11:15:44Z",
  "author_id": "security_wave_2_ops"
}
```

---

**Example 5: CONNECTION_EXHAUSTION_001 (initial state)**

```json
{
  "claim_id": "CONNECTION_EXHAUSTION_001",
  "revision_id": "CONNECTION_EXHAUSTION_001.r1",
  "prior_revision": null,
  "change_type": "initial",
  "effective_cycle": 1,
  "status": "RETAINED",
  "confidence_prior": null,
  "confidence_current": 0.95,
  "rationale": "Many stalled connections degrade/terminate mock service; reproducible with slowloris_attack.py; 100% reliability in campaign_results/20260919_103513/slowloris.log",
  "evidence_delta": null,
  "caveat_added": "Mock has no timeout enforcement; real backend timeouts unknown. Transfer depends on real backend resource limits.",
  "line_ref_updated": "docs/wiki/non-android-fuzz-findings.md line 38",
  "integrity_check": "PASS",
  "timestamp_issued": "2026-09-19T10:45:22Z",
  "author_id": "security_cycle_1_ops"
}
```

---

**Example 6: LOG_CONTROL_INJECTION_001 (initial → suppression via supersession)**

```json
{
  "claim_id": "LOG_CONTROL_INJECTION_001",
  "revision_id": "LOG_CONTROL_INJECTION_001.r1",
  "prior_revision": null,
  "change_type": "initial",
  "effective_cycle": 1,
  "status": "RETAINED",
  "confidence_prior": null,
  "confidence_current": 0.82,
  "rationale": "Unsanitized control bytes forge/alter mock log output; reproducible in log_injection_probe.py lines 88–120",
  "evidence_delta": null,
  "caveat_added": "Mock uses printf-style logging; real backend logging strategy unknown. Practical impact depends on log visibility in deployment.",
  "line_ref_updated": "docs/wiki/non-android-fuzz-findings.md line 45",
  "integrity_check": "PASS",
  "timestamp_issued": "2026-09-19T10:45:22Z",
  "author_id": "security_cycle_1_ops"
}
```

Supersession revision (splits into two narrower claims):

```json
{
  "claim_id": "LOG_CONTROL_INJECTION_001",
  "revision_id": "LOG_CONTROL_INJECTION_001.r2",
  "prior_revision": "LOG_CONTROL_INJECTION_001.r1",
  "change_type": "superseded",
  "effective_cycle": 2,
  "status": "SUPPRESSED",
  "confidence_prior": 0.82,
  "confidence_current": 0.0,
  "rationale": "Superseded by LOG_CONTROL_INJECTION_001A (mock-confirmed log injection) and LOG_CONTROL_INJECTION_001B (transfer-validation-dependent real-backend logging behavior)",
  "evidence_delta": "Split into: LOG_CONTROL_INJECTION_001A.r1 (mock-only, HIGH 0.88) and LOG_CONTROL_INJECTION_001B.r1 (transfer-pending, MEDIUM 0.65)",
  "caveat_added": "Original finding split for granularity; see superseded findings section",
  "line_ref_updated": "docs/wiki/non-android-fuzz-findings.md line 45",
  "integrity_check": "PASS",
  "timestamp_issued": "2026-09-20T13:47:22Z",
  "author_id": "security_wave_2_ops"
}
```

---

## SECTION F: Concise version-annotation JSON/YAML manifest template

**JSON manifest (machine-readable version registry):**

```json
{
  "version_manifest": {
    "manifest_version": "1.0",
    "publication_wave": 1,
    "timestamp": "2026-09-19T10:45:22Z",
    "claim_versions": [
      {
        "claim_id": "ORDERING_BYPASS_001",
        "latest_revision": "ORDERING_BYPASS_001.r2",
        "current_status": "RETAINED",
        "current_confidence": 0.93,
        "current_caveats": [
          "Unverified on real backend; ordering may be application-layer responsibility",
          "Real backend exhibits same ordering bypass; application-layer safeguards unknown"
        ],
        "revision_chain": [
          "ORDERING_BYPASS_001.r1",
          "ORDERING_BYPASS_001.r2"
        ],
        "latest_evidence_file": "endpoint_logs/20260920_run5.log",
        "latest_evidence_lines": "234–240",
        "published_to_main_table": true
      },
      {
        "claim_id": "LENGTH_DESYNC_001",
        "latest_revision": "LENGTH_DESYNC_001.r2",
        "current_status": "DOWNGRADED",
        "current_confidence": 0.72,
        "current_caveats": [
          "Mock-only fidelity gap: mock is single-threaded with no timeout enforcement",
          "Real backend may enforce frame boundary constraints; mock desync may be mock-only fidelity gap"
        ],
        "revision_chain": [
          "LENGTH_DESYNC_001.r1",
          "LENGTH_DESYNC_001.r2"
        ],
        "latest_evidence_file": "endpoint_logs/20260920_run7.log",
        "latest_evidence_lines": "456–478",
        "published_to_main_table": true,
        "downgrade_marker": true
      },
      {
        "claim_id": "HASH_OVER_READ_001",
        "latest_revision": "HASH_OVER_READ_001.r2",
        "current_status": "FALSIFIED",
        "current_confidence": 0.0,
        "current_caveats": [
          "Mock-only fidelity gap. Real backend enforces per-upload frame state."
        ],
        "revision_chain": [
          "HASH_OVER_READ_001.r1",
          "HASH_OVER_READ_001.r2"
        ],
        "latest_evidence_file": "endpoint_logs/20260920_run3.log",
        "latest_evidence_lines": "100–110",
        "published_to_main_table": false,
        "falsified_marker": true,
        "retraction_reason": "Real-endpoint testing shows no over-read; behavior is mock-only"
      }
    ],
    "summary": {
      "total_claims_tracked": 10,
      "retained": 8,
      "downgraded": 1,
      "suppressed": 0,
      "falsified": 1
    }
  }
}
```

**YAML version (human-readable alternative):**

```yaml
version_manifest:
  manifest_version: "1.0"
  publication_wave: 1
  timestamp: "2026-09-19T10:45:22Z"
  
  claims:
    ORDERING_BYPASS_001:
      latest: "ORDERING_BYPASS_001.r2"
      status: RETAINED
      confidence: 0.93
      chain: [r1, r2]
      evidence:
        file: "endpoint_logs/20260920_run5.log"
        lines: "234–240"
      published: true
      
    LENGTH_DESYNC_001:
      latest: "LENGTH_DESYNC_001.r2"
      status: DOWNGRADED
      confidence: 0.72
      chain: [r1, r2]
      evidence:
        file: "endpoint_logs/20260920_run7.log"
        lines: "456–478"
      published: true
      downgrade: true
      
    HASH_OVER_READ_001:
      latest: "HASH_OVER_READ_001.r2"
      status: FALSIFIED
      confidence: 0.0
      chain: [r1, r2]
      evidence:
        file: "endpoint_logs/20260920_run3.log"
        lines: "100–110"
        contradictory: true
      published: false
      reason: "Mock-only fidelity gap; real backend enforces frame boundaries"
      
  summary:
    total: 10
    retained: 8
    downgraded: 1
    suppressed: 0
    falsified: 1
```

---

## Repo-relative source references

**Primary sources cited in schema and examples:**

- `docs/wiki/non-android-fuzz-findings.md` lines 8–52 (finding classes, severity table, caveats)
- `docs/wiki/evidence-claim-crosswalk.md` lines 8–150 (claim extraction, no-proof markers)
- `docs/wiki/artifact-proof-index.md` lines 15–200 (confidence grading methodology, reproducibility matrix)
- `docs/wiki/non-android-fuzz-transfer-validation.md` lines 8–40 (transfer validation matrix, priority order)
- `tools/sandbox/README.md` lines 50–100 (verified results, fidelity gaps, mock-only bugs)
- `tools/sandbox/campaign_results/20260919_103513/ordering_results.json` lines 1–200 (evidence base for revisions)
- `tools/sandbox/campaign_results/20260919_103513/server.log` lines 1–4000+ (complete mock execution trace)
- `tools/sandbox/hash_framing_fuzz.py` lines 120–145 (HASH_OVER_READ_001 test implementation)
- `tools/sandbox/frame_desync_client.py` lines 156–203 (TAIL_INJECTION_001 test cases)
- `tools/sandbox/log_injection_probe.py` lines 88–120 (LOG_CONTROL_INJECTION_001 test implementation)

---

## Workflow integration checklist

Before publishing any revised claim:

- [ ] Version record includes all 14 core fields (claim_id through author_id)
- [ ] Change_type and status are consistent per Rule 3
- [ ] Prior_revision links to published prior version (or NULL for r1)
- [ ] Integrity_check = PASS or explicitly audited as AUDIT_REQUIRED
- [ ] Evidence_delta cites actual artifact file + line range (if confidence changed)
- [ ] Caveat_added is concise and appends to prior caveats (not replacing)
- [ ] Line_ref_updated points to actual modified line in wiki findings file
- [ ] Timestamp_issued is ISO 8601 UTC
- [ ] Author_id identifies operator/cycle
- [ ] If status changed, evidence_delta provides new artifact or negative-control result
- [ ] Confidence change magnitude is reasonable for change_type (e.g., upgrade +0.05–0.20)
- [ ] Publication rules D1–D8 are satisfied for main-table display

---

**This specification enables auditable, conservative claim evolution across revision cycles without loss of proof trail.**
