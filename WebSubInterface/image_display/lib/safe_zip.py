"""Zip extraction with Zip Slip rejection and size/count caps (no Slicer dependency)."""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

# Defaults sized for DICOM study zips, not archive bombs.
DEFAULT_MAX_MEMBERS = 10_000
DEFAULT_MAX_TOTAL_UNCOMPRESSED = 2 * 1024**3  # 2 GiB
_READ_CHUNK = 1024 * 1024


def safe_extract_zip(
    zf: zipfile.ZipFile,
    dest_dir: str | Path,
    *,
    max_members: int = DEFAULT_MAX_MEMBERS,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_UNCOMPRESSED,
) -> None:
    """Extract zip members under dest_dir; reject path traversal and oversized archives."""
    dest = Path(dest_dir).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    dest_prefix = str(dest)
    if not dest_prefix.endswith(os.sep):
        dest_prefix = dest_prefix + os.sep

    members = []
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        if not name or name.endswith("/"):
            continue
        members.append(info)

    if len(members) > max_members:
        raise RuntimeError(
            f"Zip has too many members ({len(members)} > {max_members})"
        )

    declared = sum(max(0, int(info.file_size or 0)) for info in members)
    if declared > max_total_bytes:
        raise RuntimeError(
            f"Zip uncompressed size too large ({declared} > {max_total_bytes})"
        )

    written = 0
    for info in members:
        name = info.filename.replace("\\", "/")
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
            while True:
                chunk = src.read(_READ_CHUNK)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_total_bytes:
                    raise RuntimeError(
                        f"Zip extract exceeded size limit ({max_total_bytes} bytes)"
                    )
                out.write(chunk)
