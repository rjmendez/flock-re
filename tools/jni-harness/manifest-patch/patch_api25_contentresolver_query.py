#!/usr/bin/env python3
"""
Patch decoded smali to replace API26+ ContentResolver query overload usage:

    query(Uri, String[], Bundle, CancellationSignal)

with the API1-safe overload:

    query(Uri, String[], String, String[], String)

Implementation strategy:
- Inject a small helper class `Api25CompatQuery` into the decoded tree.
- Rewrite matching invoke sites to call the helper.

This avoids register-shape pitfalls in direct smali rewrites and keeps patches
repeatable across APKs that share the same generated call pattern.
"""
from __future__ import annotations

import argparse
from pathlib import Path


OLD_INVOKE = (
    "Landroid/content/ContentResolver;->query("
    "Landroid/net/Uri;[Ljava/lang/String;Landroid/os/Bundle;"
    "Landroid/os/CancellationSignal;)Landroid/database/Cursor;"
)

NEW_INVOKE = (
    "Lcom/flocksafety/android/common/lib/Api25CompatQuery;->query("
    "Landroid/content/ContentResolver;Landroid/net/Uri;[Ljava/lang/String;)"
    "Landroid/database/Cursor;"
)

HELPER_SMALI = """.class public final Lcom/flocksafety/android/common/lib/Api25CompatQuery;
.super Ljava/lang/Object;
.source "Api25CompatQuery.java"

# direct methods
.method public constructor <init>()V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    return-void
.end method

.method public static query(Landroid/content/ContentResolver;Landroid/net/Uri;[Ljava/lang/String;)Landroid/database/Cursor;
    .locals 6

    move-object v0, p0
    move-object v1, p1
    move-object v2, p2
    const/4 v3, 0x0
    const/4 v4, 0x0
    const/4 v5, 0x0

    invoke-virtual/range {v0 .. v5}, Landroid/content/ContentResolver;->query(Landroid/net/Uri;[Ljava/lang/String;Ljava/lang/String;[Ljava/lang/String;Ljava/lang/String;)Landroid/database/Cursor;
    move-result-object v0
    return-object v0
.end method
"""


def patch_smali_file(path: Path) -> int:
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines(keepends=True)
    changed = 0

    for i, line in enumerate(lines):
        if OLD_INVOKE in line:
            # Example source line:
            # invoke-virtual {v1, v2, v3, v3, v3}, Landroid/content/ContentResolver;->query(...)
            lbrace = line.find("{")
            rbrace = line.find("}")
            if lbrace == -1 or rbrace == -1 or rbrace <= lbrace:
                continue
            reg_blob = line[lbrace + 1:rbrace]
            regs = [r.strip() for r in reg_blob.split(",") if r.strip()]
            if len(regs) < 3:
                continue
            lines[i] = (
                f"    invoke-static {{{regs[0]}, {regs[1]}, {regs[2]}}}, "
                f"{NEW_INVOKE}\n"
            )
            changed += 1
            continue

        # Fix-up for a previous malformed rewrite where invoke kind/regs were not adjusted.
        if "Lcom/flocksafety/android/common/lib/Api25CompatQuery;->query(" in line and "invoke-virtual" in line:
            lbrace = line.find("{")
            rbrace = line.find("}")
            if lbrace == -1 or rbrace == -1 or rbrace <= lbrace:
                continue
            reg_blob = line[lbrace + 1:rbrace]
            regs = [r.strip() for r in reg_blob.split(",") if r.strip()]
            if len(regs) < 3:
                continue
            lines[i] = (
                f"    invoke-static {{{regs[0]}, {regs[1]}, {regs[2]}}}, "
                f"{NEW_INVOKE}\n"
            )
            changed += 1

    if changed:
        path.write_text("".join(lines), encoding="utf-8")
    return changed


def ensure_helper(decoded_root: Path) -> Path:
    helper = (
        decoded_root
        / "smali_classes6"
        / "com"
        / "flocksafety"
        / "android"
        / "common"
        / "lib"
        / "Api25CompatQuery.smali"
    )
    helper.parent.mkdir(parents=True, exist_ok=True)
    helper.write_text(HELPER_SMALI, encoding="utf-8")
    return helper


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Patch decoded smali API26+ ContentResolver query calls for API25."
    )
    ap.add_argument("decoded_root", help="apktool-decoded APK root directory")
    args = ap.parse_args()

    root = Path(args.decoded_root).resolve()
    if not root.exists():
        raise SystemExit(f"decoded root does not exist: {root}")

    smali_roots = [p for p in root.glob("smali*") if p.is_dir()]
    if not smali_roots:
        raise SystemExit(f"no smali* directories under: {root}")

    total = 0
    touched_files: list[Path] = []
    for smali_dir in smali_roots:
        for smali in smali_dir.rglob("*.smali"):
            c = patch_smali_file(smali)
            if c:
                total += c
                touched_files.append(smali)

    helper = ensure_helper(root)

    print(f"decoded_root={root}")
    print(f"patched_invocations={total}")
    print(f"patched_files={len(touched_files)}")
    print(f"helper={helper}")
    for p in touched_files:
        print(p)


if __name__ == "__main__":
    main()
