# Non-Android protocol fuzz research

Index for the non-Android `tools/sandbox` research lane.

## Scope

- In scope: local protocol mock (`tools/sandbox/upload_server.py`) and companion fuzz scripts.
- Out of scope: production backend exploitation and live endpoint testing.
- Transfer checks to Android-runtime surfaces are tracked separately and may be marked
  **blocked** when target runtime prerequisites are missing.

Status labels used in this section:
- **mock-confirmed** — reproduced against local sandbox.
- **unverified-on-real** — not replayed against an authorized real target.
- **static-only** — code/docs-only observation.

## Wiki pages

- [Non-Android protocol findings](non-android-fuzz-findings.md)
- [Non-Android reproducibility](non-android-fuzz-repro.md)
- [Non-Android transfer validation](non-android-fuzz-transfer-validation.md)
- [Backend protocol](backend-protocol.md) (core protocol reference)

## Raw evidence artifacts

- `tools/sandbox/campaign_results/20260919_103513/`
- `tools/sandbox/campaign_results/20260919_103458/`
- `tools/sandbox/campaign_results/20260919_state_order_replay/`

These directories are evidence-only (logs, JSON outputs), not narrative documentation.

## See also

- [Backend protocol](backend-protocol.md) · [Security posture](security-posture.md) · [Local attack surface](local-attack-surface.md)
