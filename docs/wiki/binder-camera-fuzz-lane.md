# Binder camera fuzz lane (sandbox)

Bounded local probing for Binder camera surfaces discovered during emulator-grounded work:

- `media.camera`
- `media.camera.proxy`

Run via:

```bash
python3 tools/sandbox/binder_camera_fuzz.py --dry-run --json
python3 tools/sandbox/binder_camera_fuzz.py --execute --service media.camera --max-ops 4 --timeout-sec 5 --json
```

Safety properties:

- Default mode is dry-run (prints planned adb shell commands only).
- Execution mode is bounded by `--max-ops` and per-command timeout.
- No real-server network dependency; this lane only uses local adb shell calls.

Output is deterministic JSON (`serial`, `service`, `commands`, and `results`) so it can be used in CI/smoke gating.

