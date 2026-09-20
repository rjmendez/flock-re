# Wave 23 bounded honggfuzz blackbox campaign

## Safety gate verification
- Verified the harness remains under emulator egress control: iptables -P OUTPUT DROP and only loopback and ADB allowlist remain active.
- Evidence captured in artifact-staging/wave20-fuzz-live-launch-evidence.txt and docs/wiki/ml-models.md.

## Commands run



## Summary
- Run duration was bounded to 30 seconds with a dedicated local port 9443.
- Corpus size: 4 files under tools/sandbox/honggfuzz/runtime/blackbox/corpus.
- Crashes: 0; crash count reported by honggfuzz was 0 and the crashes directory remains empty.
- Hangs/timeouts: 0; timeout count reported by honggfuzz was 0.
- Observed metrics from the final honggfuzz summary:
  - Summary iterations:5575 time:30 speed:185 crashes_count:0 timeout_count:0 new_units_added:0 slowest_unit_ms:234 guard_nb:0 branch_coverage_percent:0 peak_rss_mb:31
- Notable anomaly: repeated MemoryError exceptions in tools/sandbox/upload_server.py while processing oversized metadata lengths; the server accepted malformed opcodes and continued, but these are robustness failures worth follow-up rather than a honggfuzz crash.
- No long unattended campaign was left running; the harness terminated cleanly within 30 seconds.
