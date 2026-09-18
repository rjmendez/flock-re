#!/usr/bin/env bash
# Reproduce the on-device capture-record schema findings:
#   1. the `assets` table has NO plate-text column (server-side OCR)
#   2. `metadata_ml` holds detection geometry/class only, never plate characters
#   3. `sensor_metadata` holds camera params only, never GPS/lat/lon/IMU
#
# INPUT: a directory of jadx-decompiled Flock system-app sources. Get it with:
#   simg2img 23_system.img system.raw && mount system.raw /mnt   # (or debugfs)
#   for a in /mnt/app/flock-*/*.apk; do jadx -d out/$(basename $a .apk) "$a"; done
# then run:  ./extract_capture_schema.sh out/
#
# Static, offline, read-only. Prints file:line anchors so every claim is checkable.
set -euo pipefail

SRC="${1:?usage: extract_capture_schema.sh <jadx-sources-dir>}"
[ -d "$SRC" ] || { echo "not a directory: $SRC" >&2; exit 1; }

hr(){ printf '\n=== %s ===\n' "$1"; }

hr "assets table columns (Room DAO INSERT binding)"
grep -rEn "metadata_ml|sensor_metadata|plate_exposure|crop_info" "$SRC" \
  --include='AssetDao_Impl.java' | head

hr "metadata_ml serializer -> DetectionResults.Detection field list"
# The Detection data class is what gets JSON-encoded into metadata_ml.
grep -rlE "class Detection\b" "$SRC" --include='Detection.java' | while read -r f; do
  echo "# $f"
  grep -nE "private|val |var |final .* [a-zA-Z]+;" "$f" | head -30
done

hr "PROOF: no plate-text field anywhere in the ML model package"
if grep -rEni "plate(Text|Number)|licenseNumber|\bocr\b|readResult|characters" \
     "$SRC" --include='*.java' \
     --include-dir=models 2>/dev/null \
     | grep -iE '/ml/lib/models/' ; then
  echo "!! unexpected: a plate-text-like field WAS found above — review it"
else
  echo "OK: zero plate-text/ocr/readResult fields in ml/lib/models (server-side OCR confirmed)"
fi

hr "NativeML JNI surface (only model name/version return strings; no getPlateText)"
grep -rEn "native .* nativeGet[A-Za-z]+|System.loadLibrary\(\"nativeML\"\)" \
  "$SRC" --include='NativeML.java' | head -30

hr "sensor_metadata serializer -> SensorMetadata field list (expect camera params, no GPS)"
grep -rlE "class SensorMetadata" "$SRC" --include='MediaAsset.java' | while read -r f; do
  echo "# $f"
  grep -nE "iso|isNight|expMs|wbGains|bracketType|fullRes|cropSettings|sensorTimestamp|AspectRatio" "$f" | head -20
done

hr "PROOF: no geographic coordinates in the asset row / SensorMetadata"
if grep -rEni "latitude|longitude|altitude|\bgps\b|imu|gyro|accel|heading|speed" \
     "$SRC" --include='MediaAsset.java' ; then
  echo "!! review the matches above — confirm they are not per-capture location fields"
else
  echo "OK: no lat/lon/GPS/IMU in MediaAsset (per-capture geotagging absent; location is a device-level system property)"
fi

hr "device-level location is a single system property, not per-capture"
grep -rEn "phonehome.location.(latitude|longitude)" "$SRC" \
  --include='FlockSystemProperties.java' | head

echo
echo "Done. Cross-check the file:line anchors above against the decompiled sources."
