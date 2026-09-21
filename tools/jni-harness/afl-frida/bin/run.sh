#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
WORK_DIR="${WORK_DIR:-$ROOT_DIR/work}"
BUILD_DIR="${BUILD_DIR:-$WORK_DIR/build}"
DEVICE_DIR="${DEVICE_DIR:-$WORK_DIR/device}"
OUT_DIR="${OUT_DIR:-$WORK_DIR/out}"
SEED_DIR="${SEED_DIR:-$WORK_DIR/seeds}"
ENV_FILE="$WORK_DIR/env.sh"

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

require_cmd adb
require_cmd afl-fuzz

HARNESS="$BUILD_DIR/native_image_utils_harness"
FRIDA_SO="$BUILD_DIR/afl-frida-trace.so"
FRIDA_JS="$DEVICE_DIR/afl.js"

if [ ! -x "$HARNESS" ]; then
  echo "error: missing harness binary: $HARNESS" >&2
  exit 1
fi

if [ ! -f "$FRIDA_SO" ]; then
  echo "error: missing afl-frida-trace.so: $FRIDA_SO" >&2
  exit 1
fi

if [ ! -f "$FRIDA_JS" ]; then
  echo "error: missing afl.js: $FRIDA_JS" >&2
  exit 1
fi

if [ -z "${TARGET_SO_PATH:-}" ] || [ ! -f "$TARGET_SO_PATH" ]; then
  echo "error: set TARGET_SO_PATH to the host path of the target shared library" >&2
  exit 1
fi

if [ "${TARGET_SYMBOL:-replace_me}" = "replace_me" ]; then
  echo "error: set TARGET_SYMBOL to the native entrypoint or adapter symbol in the target library" >&2
  exit 1
fi

if [ -z "${FRIDA_VERSION_PIN:-}" ]; then
  FRIDA_VERSION_PIN="16.1.4"
fi

if ! frida --version 2>/dev/null | grep -q "^${FRIDA_VERSION_PIN}"; then
  echo "error: Frida must be pinned to ${FRIDA_VERSION_PIN} for this target; install matching client/server first" >&2
  exit 1
fi

if ! frida-ps -U >/dev/null 2>&1; then
  echo "error: Frida cannot reach a live server on the Android target; start the matching frida-server first" >&2
  exit 1
fi

REMOTE_DIR="${REMOTE_DIR:-/data/local/tmp/flock-afl-frida}"
TARGET_SO_BASENAME="$(basename "$TARGET_SO_PATH")"

dry_run=0
if [ "${1:-}" = "--dry-run" ]; then
  dry_run=1
fi

adb shell "mkdir -p '$REMOTE_DIR'"
adb push "$HARNESS" "$REMOTE_DIR/native_image_utils_harness" >/dev/null
adb push "$FRIDA_SO" "$REMOTE_DIR/afl-frida-trace.so" >/dev/null
adb push "$FRIDA_JS" "$REMOTE_DIR/afl.js" >/dev/null
adb push "$TARGET_SO_PATH" "$REMOTE_DIR/$TARGET_SO_BASENAME" >/dev/null
adb shell "chmod 755 '$REMOTE_DIR/native_image_utils_harness' '$REMOTE_DIR/afl-frida-trace.so'"

cmd="cd '$REMOTE_DIR' && TARGET_SO_PATH='./$TARGET_SO_BASENAME' TARGET_SYMBOL='$TARGET_SYMBOL' TARGET_CALL_MODE='${TARGET_CALL_MODE:-image_frame}' AFL_FRIDA_JS_SCRIPT='./afl.js' AFL_DEBUG_CHILD=1 LD_PRELOAD='./afl-frida-trace.so' ./native_image_utils_harness"

echo "device command: $cmd"

if [ "$dry_run" -eq 1 ]; then
  exit 0
fi

mkdir -p "$OUT_DIR"

afl-fuzz -O -i "$SEED_DIR" -o "$OUT_DIR" -m none -t "${AFL_TIMEOUT:-1000}" -- adb shell "$cmd"
