#!/usr/bin/env bash
# Provision an Android 8.1 (API 27) emulator and install the extracted Flock APKs.
# Run on a host WITH /dev/kvm (this WSL2 box has none). Requires the Android SDK
# (cmdline-tools, platform-tools, emulator) on PATH and $ANDROID_HOME set.
#
# APK_DIR must point at the Flock APKs pulled from the firmware's system/priv-app
# (e.g. via simg2img 24_system.img + mount, then copy flock-*.apk).
set -euo pipefail

API=27
ABI="${ABI:-x86_64}"          # x86_64 is fastest under KVM; use arm64-v8a to run the ARM native libs natively
PKG="system-images;android-${API};google_apis;${ABI}"
AVD="${AVD:-flock27}"
APK_DIR="${APK_DIR:?set APK_DIR to the folder of extracted flock-*.apk files}"

command -v sdkmanager >/dev/null || { echo "sdkmanager not on PATH (Android SDK cmdline-tools)"; exit 1; }
[ -e /dev/kvm ] || echo "WARNING: /dev/kvm missing — the emulator will be unusably slow or fail."

yes | sdkmanager "$PKG" "platform-tools" "platforms;android-${API}" >/dev/null
echo no | avdmanager create avd -n "$AVD" -k "$PKG" --force

# Writable system so debuggable apps + Frida server can be pushed.
emulator -avd "$AVD" -no-snapshot -writable-system -no-boot-anim &
adb wait-for-device
until [ "$(adb shell getprop sys.boot_completed | tr -d '\r')" = "1" ]; do sleep 2; done
adb root

for apk in "$APK_DIR"/flock-*.apk; do
  echo "installing $(basename "$apk")"
  adb install -r -g "$apk" || echo "  (install failed — may need its dependencies first)"
done

echo "AVD $AVD ready. All Flock apps ship debuggable=true, so you can jdb/Frida-attach."
echo "Next: push a frida-server matching the ABI, then: frida -U -f <pkg> -l frida_hooks.js"
