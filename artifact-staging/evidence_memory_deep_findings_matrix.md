# evidence-memory deep findings matrix

Date: 2026-09-20

Scope:
- `flock-re-fde-unlocked-bootloader`
- `flock-re-online-source-factcheck`
- Existing evidence-memory-produced artifacts and claim matrices already in this repo

Note:
- Additional live evidence-memory reflect/reason calls intermittently timed out in this session, so this matrix is synthesized from successfully persisted evidence-memory outputs plus existing evidence anchors.

## Consolidated claim matrix

| Domain | Claim | Status | Confidence | Evidence anchors | Deterministic next check |
|---|---|---|---|---|---|
| Boot trust | Device is locked + AVB2-enforced | Contradicted | High | `artifact-staging/online_evidence-memory_factcheck_matrix.md` (C1), `docs/wiki/boot-chain.md` | Capture fresh hardware boot-state outputs and archive raw evidence. |
| FDE practical risk | Unlocked bootloader reduces practical FDE assurance | Corroborated (inference) | Medium-High | `artifact-staging/online_evidence-memory_factcheck_matrix.md` (C4), `artifact-staging/unlocked_bootloader_fde_bypass_simulation.md` | Tie inference to live measured boot/runtime controls and classify residual risk. |
| FDE overclaim guard | Unlocked bootloader alone proves universal direct `/data` decrypt | Contradicted | High | `artifact-staging/online_evidence-memory_factcheck_matrix.md` (C2) | Controlled extraction experiment on matching build/hardware with full artifact trail. |
| Local exposure | Provider/export surfaces expose sensitive local paths | Corroborated | High | `artifact-staging/online_evidence-memory_factcheck_matrix.md` (C3), `artifact-staging/identity_chain_expansion.md` | Non-privileged read/write enforcement tests with allow/deny and audit logs. |
| External PoC claims | Public PoC proves end-to-end extraction on exact build | Unverified | Medium | `artifact-staging/online_evidence-memory_factcheck_matrix.md` (C5) | Reproduce against matched hardware/build hashes and verify outputs deterministically. |
| OTA governance | Version-floor/signer-domain/auth parity invariants are enforced | Unverified | High | `artifact-staging/ota_governance_expansion.md` | API matrix tests for downgrade rejection, signer mismatch handling, auth mode parity. |
| Retention/privacy | Cleanup covers media-db/kernel-oops sensitive artifacts | Unverified | High | `artifact-staging/privacy_retention_gaps.md` | Generate artifacts -> run cleanup trigger -> verify residue/cleanup behavior. |
| Reset persistence | Factory reset guarantees purge of `/persist` control artifacts | Unverified | Medium | `artifact-staging/physical_chain_expansion.md`, `privacy_retention_gaps.md` | Pre/post reset hash and inventory for `/persist/flock/auth0/*`. |

## Highest-value unresolved gaps (top 5)
1. Runtime authorization enforcement for `core_values` read/write.
2. OTA backend policy invariants (version floor, signer-domain, fallback auth parity).
3. Live boot-trust attestation on current hardware image.
4. SELinux/runtime readability boundary for exported diagnostics artifacts.
5. Credential lifecycle validation (rotation/revocation effectiveness).

## Practical sequencing
1. Close `core_values` runtime authz boundary.
2. Close OTA policy matrix.
3. Collect live boot-state evidence.
4. Run retention + reset persistence checks.
5. Reassess severity/confidence after closures.

