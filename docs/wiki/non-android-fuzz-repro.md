# Non-Android reproducibility

Minimal replay commands for the non-Android sandbox findings.

## Baseline setup

```bash
cd tools/sandbox
python3 upload_server.py --port 8443 --cert server.pem
```

Open a second terminal for probes.

## Replay commands

```bash
python3 ordering_attack_client.py --port 8443 --out ordering_results.json
python3 hello_ack_probe.py --port 8443 --ack 12
python3 neg_zero_length_probe.py --port 8443 --out neg_zero_results.json
python3 hash_framing_fuzz.py --port 8443 --out hash_results.json
python3 frame_desync_client.py --port 8443
python3 slowloris_attack.py --port 8443 --connections 50 --hold 20 --canary
python3 log_injection_probe.py --port 8443
```

## Expected signals

- Ordering/ack probes: invalid order or non-OK continuation byte still accepted in mock.
- Length/hash/desync probes: parser desync behavior and hold conditions.
- Slowloris probe: resource pressure and service responsiveness degradation.
- Log-injection probe: formatting/control-byte effects in unsanitized logs.

## Recorded artifact sets

- `tools/sandbox/campaign_results/20260919_103513/`
- `tools/sandbox/campaign_results/20260919_103458/`
- `tools/sandbox/campaign_results/20260919_state_order_replay/`

These directories contain captured logs/JSON from executed campaigns.

## Tooling update

- Campaign execution now requires explicit evidence capture per run:
  1. exact command(s),
  2. artifact output path(s),
  3. key output lines used for classification.
- For Android-runtime transfer probes (camera/reaperd lanes), run preflight checks before claiming
  coverage:
  - pin target serial (`ANDROID_SERIAL=<serial>`),
  - verify required runtime socket exists,
  - verify on-target probe transport supports required socket mode.
- If preflight fails, classify the lane as **blocked** (not **done**) and record the exact blocker.

Concrete preflight commands:

```bash
python3 tools/sandbox/binder_camera_fuzz.py --json
python3 tools/sandbox/reaperd_wire_probe.py --json
```

Endpoint-map lane quality gate (must pass before marking done):

```bash
python3 tools/sandbox/endpoint_map_quality_gate.py \
  --analysis-json artifact-staging/fleetlog_real_corpus/full_crashpack_analysis.json \
  --json-out artifact-staging/results/endpoint_map_quality_gate.json
```

### Local endpoint preflight (required for local-model evidence claims)

Use this handshake check before claiming any lane used local-model assistance via a local MCP-compatible endpoint:

```bash
python3 - <<'PY'
import requests
u="http://127.0.0.1:8000/mcp"
h={"Accept":"application/json, text/event-stream","Content-Type":"application/json"}
init={
  "jsonrpc":"2.0",
  "id":1,
  "method":"initialize",
  "params":{
    "protocolVersion":"2025-03-26",
    "clientInfo":{"name":"lane-preflight","version":"1.0"},
    "capabilities":{}
  }
}
r=requests.post(u,headers=h,json=init,timeout=10)
print("status:", r.status_code)
print("mcp-session-id:", r.headers.get("mcp-session-id"))
print((r.text or "")[:240])
PY
```

Expected signal for a healthy endpoint:
- HTTP `200`,
- response `Content-Type: text/event-stream`,
- `mcp-session-id` header present,
- JSON-RPC `initialize` result includes server info.

If this preflight fails, mark the lane **blocked** for MCP/tooling and do not claim local-model usage.

## Boundaries

Replay commands target the local research mock only. Results are **mock-confirmed** and
**unverified-on-real** until transfer tests are executed.
