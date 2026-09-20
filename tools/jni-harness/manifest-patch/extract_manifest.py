#!/usr/bin/env python3
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "android-fs/system/app/flock-object/flock-object.apk"
OUT = Path(__file__).resolve().parent / "rawmanifest/AndroidManifest.xml.bin"
OUT.parent.mkdir(parents=True, exist_ok=True)

z = zipfile.ZipFile(SRC)
info = z.getinfo("AndroidManifest.xml")
print("compress_type", info.compress_type, "size", info.file_size, "compress_size", info.compress_size)
data = z.read("AndroidManifest.xml")
OUT.write_bytes(data)
print("written", len(data), "to", OUT)
