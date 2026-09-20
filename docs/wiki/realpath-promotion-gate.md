# Real-path promotion gate and data handling

## Purpose
Prevent mock/harness findings from being promoted as final security conclusions, and prevent raw device data from being published in repository artifacts.

## Promotion rule
- Findings from mock, replay, fuzz harness, or partially staged corpora are **provisional**.
- A finding is **real-path-backed** only when reproducible evidence exists from mounted/decrypted/runtime-real sources for the exact claim.
- If real-path evidence contradicts a provisional claim, the claim must be downgraded/retracted immediately.

## Public-repo data handling rule
- Do **not** publish raw device logs, raw coordinates, tokens, credential-like values, or secret-bearing lines.
- Public docs may include only:
  - class-level presence/absence statements,
  - aggregate counts,
  - redacted placeholders,
  - reproducible method notes.

## Private processing rule
- Full-fidelity processing of real device data is allowed only in private/non-repo paths.
- Derived public summaries must be redacted before landing in repository content.

## Required checklist before promoting a claim
1. Source corpus completeness verified for the claim scope.
2. Required decrypt/mount/runtime prerequisites satisfied.
3. Deterministic scans/tests run and reproducible.
4. Claim language matches actual evidence tier.
5. Public output passes redaction checks.

If any checklist item fails, status remains **provisional** or **blocked-by-missing-corpus**.
