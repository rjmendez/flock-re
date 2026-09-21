# Non-Android protocol findings

Findings from sandbox protocol campaigns in `tools/sandbox`.
All core items below are **mock-confirmed** and **unverified-on-real** unless noted.

## Confirmed finding classes

1. **Ordering/state bypass**  
   The mock accepts protocol operations out of order, including pre-HELLO sequences.

2. **Length-prefix desynchronization**  
   Non-positive declared lengths can desynchronize frame consumption and opcode parsing.

3. **HASH frame boundary faults**  
   Over-read smuggling and under-read holds are reproducible at the fixed 32-byte HASH boundary.

4. **Valid-short-frame tail injection**  
   A valid short FILE frame with appended bytes can inject follow-on protocol behavior.

5. **Connection-exhaustion susceptibility**  
   Many stalled connections can degrade or terminate mock service availability.

6. **HELLO continuation-byte acceptance**  
   Non-OK continuation-byte values are accepted in the mock.

7. **Log control-byte injection**  
   Unsanitized control bytes can forge/alter mock log output formatting.

## Exploitability grading (research triage)

| Finding class | Severity | Exploitability (0-10) | Reliability | Scope label |
|---|---:|---:|---|---|
| Ordering/state bypass | High | 8 | High | Mock-confirmed, unverified-on-real |
| Length-prefix desync | High | 7 | High | Mock-confirmed, unverified-on-real |
| HASH over-read smuggling | High | 7 | High | Mock-confirmed, unverified-on-real |
| HASH under-read hold | Medium | 6 | High | Mock-confirmed, unverified-on-real |
| Valid-short-frame tail injection | High | 8 | High | Mock-confirmed, unverified-on-real |
| Connection exhaustion | High | 9 | High | Mock-confirmed, deployment-dependent transfer |
| HELLO continuation-byte acceptance | Medium | 6 | High | Mock-confirmed, unverified-on-real |
| Log control-byte injection | Medium | 6 | High | Mock-confirmed, sink-dependent transfer |

## Caveats

- These findings do not by themselves prove production compromise.
- Transfer to real targets requires controlled replay against authorized endpoints.
- This page is research reporting, not remediation guidance.

## Evidence references

- `tools/sandbox/README.md`
- `tools/sandbox/campaign_results/20260919_103513/ordering_results.json`
- `tools/sandbox/campaign_results/20260919_103513/server.log`
- `tools/sandbox/campaign_results/20260919_103513/slowloris_attack.log`
