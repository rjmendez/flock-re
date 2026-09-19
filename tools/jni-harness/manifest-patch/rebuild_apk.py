#!/usr/bin/env python3
"""
Rebuild flock-object.apk with ONLY AndroidManifest.xml replaced by the
byte-patched version (single minSdkVersion attribute changed). Every other
zip entry (classes*.dex, resources.arsc, res/*, assets/*, lib/*, etc.) is
copied byte-for-byte from the original, at the same compression method, so
nothing else in the APK changes. Original META-INF/ signature files are
dropped (the signature is invalidated by the manifest edit regardless; a
fresh signature is applied afterwards with apksigner).
"""
import sys
import zipfile

SRC_APK = '/home/rjmendez/flock-alpr/re/android-fs/system/app/flock-object/flock-object.apk'
PATCHED_MANIFEST = '/home/rjmendez/flock-alpr/re/deep/swarm/jni-harness/patch/rawmanifest/AndroidManifest.xml.patched.bin'
OUT_APK = sys.argv[1] if len(sys.argv) > 1 else '/home/rjmendez/flock-alpr/re/deep/swarm/jni-harness/patch/flock-object-patched-unsigned.apk'

with open(PATCHED_MANIFEST, 'rb') as f:
    patched_manifest = f.read()

zin = zipfile.ZipFile(SRC_APK, 'r')
changed = []
skipped_signing = []
with zipfile.ZipFile(OUT_APK, 'w', allowZip64=True) as zout:
    for item in zin.infolist():
        name = item.filename
        if name.startswith('META-INF/') and (
            name.endswith('.RSA') or name.endswith('.DSA') or name.endswith('.EC')
            or name.endswith('.SF') or name == 'META-INF/MANIFEST.MF'
        ):
            skipped_signing.append(name)
            continue
        data = zin.read(name)
        if name == 'AndroidManifest.xml':
            assert data != patched_manifest
            data = patched_manifest
            changed.append(name)
        # Preserve original compression method and other zip metadata exactly.
        new_info = zipfile.ZipInfo(name, date_time=item.date_time)
        new_info.compress_type = item.compress_type
        new_info.external_attr = item.external_attr
        new_info.internal_attr = item.internal_attr
        new_info.create_system = item.create_system
        zout.writestr(new_info, data)

print('changed entries:', changed)
print('dropped original signing entries:', skipped_signing)
print('wrote', OUT_APK)
