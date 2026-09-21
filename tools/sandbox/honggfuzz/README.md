# honggfuzz upload-protocol fuzzing

This subtree adds a Tier-3 fuzzing scaffold for the capture-upload protocol surface.
It is split into two workflows:

1. **Black-box replay** — honggfuzz mutates raw post-HELLO protocol bytes and a Python
   driver replays them against the existing `upload_server.py` mock.
2. **Coverage-guided netdriver** — a tiny C server/parser scaffold (`upload_netdriver.c`)
   gives honggfuzz a concrete netdriver target with deterministic paths and stateful
   protocol branches.

Both workflows are sandbox-only. They never require a real token or a real device.

## Prerequisites

- Python 3.10+ for the wrappers and replay client
- `honggfuzz` in `PATH`
- `hfuzz-clang`/`hfuzz-gcc` from a honggfuzz build if you want the guided netdriver
  target to behave like a real honggfuzz build
- A C compiler for the scaffold sanity check

## Layout

| File | Purpose |
|---|---|
| `seed_upload_corpus.py` | Writes deterministic seed corpus files for both workflows |
| `replay_upload_file.py` | File-mode black-box replay driver; prepends a fixed HELLO and sends mutated bytes verbatim |
| `run_blackbox.py` | Starts the Python mock server, seeds corpus/output directories, and launches honggfuzz in `-x` mode |
| `upload_netdriver.c` | Minimal C netdriver-compatible server/parser scaffold |
| `run_coverage.py` | Seeds corpus/output directories, builds the C scaffold, and launches honggfuzz with `--netdriver` |

## Black-box workflow

The black-box path is the quickest way to exercise the upload surface without compiling
anything new. It treats the fuzz file as raw post-HELLO protocol traffic.

```bash
python3 tools/sandbox/honggfuzz/run_blackbox.py --dry-run
python3 tools/sandbox/honggfuzz/run_blackbox.py
```

The wrapper uses these defaults:

- server: `tools/sandbox/upload_server.py --plaintext`
- corpus: `tools/sandbox/honggfuzz/runtime/blackbox/corpus`
- output: `tools/sandbox/honggfuzz/runtime/blackbox/output`
- workspace: `tools/sandbox/honggfuzz/runtime/blackbox/workspace`
- crashdir: `tools/sandbox/honggfuzz/runtime/blackbox/crashes`

The exact honggfuzz command is printed before execution. The file-replay driver always
prepends a deterministic HELLO handshake, then sends the fuzzed bytes verbatim to the mock.

## Additional probe routes (GPS/log + protocol/control)

Use the route wrapper to run undercovered surfaces from deterministic entrypoints:

```bash
python3 tools/sandbox/honggfuzz/run_surface_routes.py gps-log --dry-run
python3 tools/sandbox/honggfuzz/run_surface_routes.py protocol-control --dry-run --plaintext --port 8443 --ack 12
```

Route defaults:

- `gps-log`: scans `tools/sandbox/campaign_results` with `crashpack_coordinate_probe.py`
- `protocol-control`: runs `hello_ack_probe.py` with a bogus HELLO-ack byte (default `12`)

## Coverage-guided workflow

The guided path needs the C scaffold so honggfuzz can observe coverage inside a small
parser with real branches.

```bash
python3 tools/sandbox/honggfuzz/run_coverage.py --dry-run
python3 tools/sandbox/honggfuzz/run_coverage.py
```

The wrapper uses these defaults:

- corpus: `tools/sandbox/honggfuzz/runtime/coverage/corpus`
- output: `tools/sandbox/honggfuzz/runtime/coverage/output`
- workspace: `tools/sandbox/honggfuzz/runtime/coverage/workspace`
- crashdir: `tools/sandbox/honggfuzz/runtime/coverage/crashes`
- target binary: `tools/sandbox/honggfuzz/upload_netdriver`
- listen port: `8443`

To build manually with a honggfuzz checkout/wrapper, the intended compile line is:

```bash
hfuzz-clang -O1 -g -Wall -Wextra -o tools/sandbox/honggfuzz/upload_netdriver \
  tools/sandbox/honggfuzz/upload_netdriver.c
```

Then launch honggfuzz with netdriver support:

```bash
HFND_TCP_PORT=8443 honggfuzz --netdriver -i tools/sandbox/honggfuzz/runtime/coverage/corpus \
  --output tools/sandbox/honggfuzz/runtime/coverage/output \
  --workspace tools/sandbox/honggfuzz/runtime/coverage/workspace \
  --crashdir tools/sandbox/honggfuzz/runtime/coverage/crashes \
  -- tools/sandbox/honggfuzz/upload_netdriver --port 8443
```

## Known limitations

- The black-box path exercises the real Python mock, but honggfuzz only sees the replay
  driver’s process behavior. It does **not** provide protocol-parser coverage inside the
  Python mock.
- The C netdriver target is a minimal scaffold, not a full emulation of the device’s
  transport, TLS, or backend auth checks.
- The coverage-guided path expects `HFND_TCP_PORT` to match the target’s bind port. The
  wrapper sets that for you; the manual command above does it explicitly.
- The coverage-guided path prefers `hfuzz-clang`/`hfuzz-gcc`. If only `cc` is available,
  the wrapper can still produce a local smoke build, but that is not a substitute for a
  proper honggfuzz-instrumented build.
- Both workflows assume localhost-only execution and plaintext transport for the mock.
- The corpus seeds are synthetic and intentionally small; they are meant to bootstrap
  mutation, not to model real captures.
