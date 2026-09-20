# Non-Android transfer validation

Mock-to-real transfer plan for protocol findings. This is a research validation matrix, not a
claim that production behavior matches the mock.

## Transfer matrix

| Finding class | Candidate real surface | Validation method | Success criterion | Falsification criterion |
|---|---|---|---|---|
| Ordering/state bypass | Real upload parser path described in backend protocol docs | Replay out-of-order sequence from `ordering_attack_client.py` | Invalid order rejected/state-gated | Invalid order accepted as valid flow |
| Length-prefix desync | Real length-prefixed frame parser | Send non-positive lengths with trailing payload bytes | Malformed frame rejected and session closed | Trailing bytes reinterpreted as opcodes |
| HASH over-read smuggling | Real HASH-frame consumer | Send 33-byte HASH payload | Trailing byte ignored/rejected | Trailing byte treated as next opcode |
| HASH under-read hold | Real HASH-frame consumer | Send 31-byte HASH then delay final byte | Timeout/abort enforced | Worker/session stalls awaiting missing byte |
| Valid-short-frame tail injection | Real FILE/METADATA framing path | Send short valid frame plus tail bytes | Tail isolated/rejected | Tail influences next opcode handling |
| HELLO continuation-byte acceptance | Real continuation-byte handling | Send non-OK continuation-byte variants | Invalid values rejected | Invalid values accepted through full flow |
| Connection exhaustion | Real ingress/worker model | Concurrent stalled-body sessions | Limits/timeouts prevent service failure | Listener or worker exhaustion observed |

## Priority order

1. Ordering + length + HASH boundary classes (highest transfer value).
2. Connection-exhaustion behavior under real ingress controls.
3. Continuation-byte validation.

## Boundaries

- Real parser/backend implementation is not present in this repository.
- All current findings are **mock-confirmed** and **unverified-on-real**.
- Transfer requires authorized endpoint access and controlled test conditions.

## Source references

- `docs/wiki/backend-protocol.md`
- `tools/sandbox/README.md`
- `docs/wiki/non-android-fuzz-findings.md`
