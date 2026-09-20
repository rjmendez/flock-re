# Evidence-memory claims crosswalk (public-facing, evidence-bounded)

Date: 2026-09-20  
Status legend: **Corroborated** = supported by current evidence; **Contradicted** = evidence shows claim is false/inaccurate; **Unverified** = plausible or asserted but not yet proven.

| Claim | Source evidence | Status | Confidence | Next test |
|---|---|---|---|---|
| Device is currently locked with AVB2-enforced verified boot. | `online_evidence_memory_factcheck_matrix.md` (C1 classified contradicted); `wave23_unlocked_bootloader_fde_bypass_simulation.md` (weak boot-trust indicators). | **Contradicted** | High | Collect fresh hardware boot attest outputs (`fastboot` lock state, AVB/verity indicators) and archive results. |
| Unlocked bootloader alone proves complete direct `/data` decryption/extraction on this build. | `online_evidence_memory_factcheck_matrix.md` (C2 contradicted); `wave23_unlocked_bootloader_fde_bypass_simulation.md` (bounded to likely runtime compromise, not universal direct proof). | **Contradicted** | High | Run controlled live extraction experiment with strict preconditions and capture full artifact trail. |
| Provider/export surfaces can expose sensitive local identity data paths. | `online_evidence_memory_factcheck_matrix.md` (C3 corroborated); `wave24_identity_chain_expansion.md` (exported provider + read path). | **Corroborated** | High | Verify exact read scope from non-privileged app context and document controls that block or allow access. |
| Weak boot trust materially reduces practical FDE assurance even without proving a full direct bypass. | `online_evidence_memory_factcheck_matrix.md` (C4 corroborated inference); `wave23_unlocked_bootloader_fde_bypass_simulation.md`; `wave24_physical_chain_expansion.md`. | **Corroborated** | Medium | Link simulated chain to live-device measurements and classify residual risk with validated preconditions. |
| Public PoC currently proves end-to-end decrypted extraction on this exact build/hardware profile. | `online_evidence_memory_factcheck_matrix.md` (C5 unverified). | **Unverified** | Medium | Reproduce PoC on matching build hash/hardware and retain deterministic logs/output hashes. |
| `core_values` write path can be used for endpoint/token tampering that affects downstream clients. | `wave24_identity_chain_expansion.md` (likely chain C2, code anchors for insert/update + downstream use). | **Unverified** | Medium | Attempt controlled write mutation and verify whether downstream auth/upload client behavior changes. |
| OTA backend enforces immutable version floors and signer-domain authorization for every update request. | `wave24_ota_governance_expansion.md` (explicitly unverified backend invariants). | **Unverified** | High | Execute API policy test matrix for floor checks, signer-domain mismatches, and rejection behavior. |
| Bearer mode and fallback auth mode are equally constrained by backend authorization policy. | `wave24_ota_governance_expansion.md` (dual auth paths proven, parity unverified). | **Unverified** | Medium | Compare endpoint authorization outcomes for bearer vs fallback with identical principal context. |
| Factory reset guarantees removal of `/persist`-stored identity/control artifacts. | `wave24_physical_chain_expansion.md` (persistence-by-omission likely); `wave25_privacy_retention_gaps.md` (persisted auth artifacts + reset residue concern). | **Unverified** | Medium | Collect pre/post reset filesystem evidence for `/persist/flock/auth0/*`. |
| Retention cleanup currently covers exported `media-db` and `kernel-oops` artifacts. | `wave25_privacy_retention_gaps.md` (cleanup scope vs artifact generation mismatch). | **Unverified** | High | Trigger cleanup cycle after generating artifacts; verify file deletion/retention outcomes. |
| Exported diagnostics flow can be read by third-party unprivileged apps on enforcing builds. | `wave24_physical_chain_expansion.md` (export operation corroborated); `wave25_runtime_boundary_gaps.md` + `wave25_privacy_retention_gaps.md` (readability boundary unresolved). | **Unverified** | Medium | Attempt read from untrusted app UID and capture SELinux audit allow/deny lines. |
| `reaperd` socket exposure leads to materially privileged command side effects. | `wave24_physical_chain_expansion.md` (socket exposure likely risk); `wave25_runtime_boundary_gaps.md` (side-effect closure outstanding). | **Unverified** | Medium | Execute bounded command semantics test and measure concrete side effects. |
| Persisted device machine credentials and token metadata indicate governance lifecycle gaps. | `wave25_supplychain_secret_gaps.md` (credential persistence + rotation/revocation evidence gap). | **Corroborated** | High | Validate live rotation/revocation workflow and aging/invalidated records for device credentials. |
| Most online high-signal claims overlap existing local evidence; novelty is limited and targeted. | `online_relevance_factcheck_scope_synthesis.md` (coverage statistics + one net-new candidate), `online_source_harvest_relevance.md` (high-overlap source map). | **Corroborated** | High | Maintain claim-to-anchor inventory and retest only unmatched/new claims. |

## Notes for PR language

- Use “corroborated/contradicted/unverified” exactly as above.
- Keep unresolved items conditional; avoid asserting exploitation success without runtime proof.
- Keep focus on reproducible evidence anchors and deterministic closure tests.


