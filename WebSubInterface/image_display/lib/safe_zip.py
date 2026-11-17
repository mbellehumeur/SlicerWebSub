"""Zip extraction with Zip Slip rejection (no Slicer dependency)."""

from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path


def safe_extract_zip(zf: zipfile.ZipFile, dest_dir: str | Path) -> None:
    """Extract zip members under dest_dir; reject path traversal."""
    dest = Path(dest_dir).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    dest_prefix = str(dest)
    if not dest_prefix.endswith(os.sep):
        dest_prefix = dest_prefix + os.sep
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        if not name or name.endswith("/"):
            continue
        parts = [p for p in name.split("/") if p and p != "."]
        if not parts:
            continue
        if ".." in parts:
            raise RuntimeError(f"Unsafe zip path: {info.filename}")
        target = (dest / Path(*parts)).resolve()
        if target != dest and not str(target).startswith(dest_prefix):
            raise RuntimeError(f"Unsafe zip path: {info.filename}")
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(info, "r") as src, open(target, "wb") as out:
            shutil.copyfileobj(src, out)
