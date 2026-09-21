#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
WORK_DIR="${WORK_DIR:-$ROOT_DIR/work}"
BUILD_DIR="${BUILD_DIR:-$WORK_DIR/build}"
DEVICE_DIR="${DEVICE_DIR:-$WORK_DIR/device}"
LOG_DIR="${LOG_DIR:-$WORK_DIR/logs}"
ENV_FILE="$WORK_DIR/env.sh"
TARGET_SRC="$ROOT_DIR/src/native_image_utils_harness.c"
HARNESS_OUT="$BUILD_DIR/native_image_utils_harness"
FRIDA_JS_OUT="$BUILD_DIR/afl.js"
FRIDA_SO_OUT="$BUILD_DIR/afl-frida-trace.so"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "error: missing required command: $1" >&2
    exit 1
  }
}

if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  . "$ENV_FILE"
fi

require_cmd python3
require_cmd make

if [ -z "${ANDROID_NDK_ROOT:-}" ] || [ ! -d "${ANDROID_NDK_ROOT:-}" ]; then
  echo "error: set ANDROID_NDK_ROOT (or ANDROID_NDK_HOME) to an installed Android NDK" >&2
  exit 1
fi

if [ -z "${AFLPP_ROOT:-}" ] && [ -z "${AFL_FRIDA_TRACE_SO:-}" ]; then
  echo "error: set AFLPP_ROOT to a local AFL++ checkout, or AFL_FRIDA_TRACE_SO to a built afl-frida-trace.so" >&2
  exit 1
fi

mkdir -p "$BUILD_DIR" "$DEVICE_DIR" "$LOG_DIR"

python3 - "$FRIDA_JS_OUT" <<'PY'
from pathlib import Path
import sys

out = Path(sys.argv[1])
out.write_text(
    """'use strict';

Afl.print('flock-re AFL++ Frida bootstrap: enabling in-memory fuzzing');
Afl.setInstrumentLibraries();
Afl.setInMemoryFuzzing();
Afl.setStatsInterval(1);

const entry = DebugSymbol.fromName('LLVMFuzzerTestOneInput');
if (entry.address.equals(ptr(0))) {
    Afl.error('Cannot find LLVMFuzzerTestOneInput in the harness');
}

const cm = new CModule(`
    extern unsigned char * __afl_fuzz_ptr;
    extern unsigned int * __afl_fuzz_len;
    extern void LLVMFuzzerTestOneInput(unsigned char *buf, unsigned long len);

    void afl_entry(void) {
        LLVMFuzzerTestOneInput(__afl_fuzz_ptr, *__afl_fuzz_len);
    }
    `,
    {
        LLVMFuzzerTestOneInput: entry.address,
        __afl_fuzz_ptr: Afl.getAflFuzzPtr(),
        __afl_fuzz_len: Afl.getAflFuzzLen()
    });

Afl.setEntryPoint(cm.afl_entry);
Afl.setJsMainHook(cm.afl_entry);
Afl.done();
"""
)
PY

cc="${ANDROID_NDK_ROOT}/toolchains/llvm/prebuilt"
host_tag=""
case "$(uname -s | tr '[:upper:]' '[:lower:]')" in
  mingw*|msys*|cygwin*)
    host_tag="windows-x86_64"
    ;;
  darwin*)
    host_tag="darwin-x86_64"
    ;;
  *)
    host_tag="linux-x86_64"
    ;;
esac

clang="$cc/$host_tag/bin/armv7a-linux-androideabi25-clang"
if [ ! -x "$clang" ]; then
  echo "error: NDK clang not found at $clang" >&2
  exit 1
fi

"$clang" -fPIE -pie -O2 -Wall -Wextra -Werror -D_FILE_OFFSET_BITS=64 \
  -o "$HARNESS_OUT" "$TARGET_SRC" -ldl

if [ -n "${AFL_FRIDA_TRACE_SO:-}" ]; then
  cp "$AFL_FRIDA_TRACE_SO" "$FRIDA_SO_OUT"
else
  afl_mode_dir="$AFLPP_ROOT/frida_mode"
  if [ ! -d "$afl_mode_dir" ]; then
    echo "error: AFLPP_ROOT does not contain frida_mode/: $AFLPP_ROOT" >&2
    exit 1
  fi

  make -C "$afl_mode_dir" clean >/dev/null
  make -C "$afl_mode_dir" arm >/dev/null

  built_so="$afl_mode_dir/afl-frida-trace.so"
  if [ ! -f "$built_so" ]; then
    built_so="$afl_mode_dir/build/afl-frida-trace.so"
  fi

  if [ ! -f "$built_so" ]; then
    echo "error: could not find built afl-frida-trace.so after make -C $afl_mode_dir arm" >&2
    exit 1
  fi

  cp "$built_so" "$FRIDA_SO_OUT"
fi

cp "$FRIDA_JS_OUT" "$DEVICE_DIR/afl.js"

echo "built harness:   $HARNESS_OUT"
echo "built frida so:  $FRIDA_SO_OUT"
echo "staged afl.js:   $DEVICE_DIR/afl.js"
echo "next: set TARGET_SO_PATH and TARGET_SYMBOL, then run bin/run.sh --dry-run"
