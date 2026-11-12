#!/usr/bin/env python3
"""Pack hub SPA folders into spa-<folder>.zip assets for the spa-clients release.

Expects trees already synced under hub/ (index.html present). Does not build
or sync from sibling repos — use prepare_spa_release.py or make_zip.py first.

Usage (from anywhere):
    python WebSubInterface/hub/scripts/pack_spa_release_assets.py
    python WebSubInterface/hub/scripts/pack_spa_release_assets.py --output-dir dist/spa
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

# Keep in sync with Lib/spa_download.SPA_DOWNLOAD_CATALOG folders.
SPA_FOLDERS = (
    "worklist-client",
    "reporting-client",
    "classroom-client",
    "slicerlive",
    "hub-mirror",
    "slim",
    "OHIF-client",
)

EXCLUDED_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".map"}
EXCLUDED_FILE_NAMES = {".DS_Store", "Thumbs.db"}


def hub_dir_from_script() -> Path:
    # scripts/ -> hub/
    return Path(__file__).resolve().parent.parent


def should_include(rel: Path) -> bool:
    if set(rel.parts) & EXCLUDED_DIR_NAMES:
        return False
    if rel.name in EXCLUDED_FILE_NAMES:
        return False
    if rel.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    return True


def asset_name(folder: str) -> str:
    return f"spa-{folder}.zip"


def pack_folder(src: Path, zip_path: Path) -> int:
    """Zip contents of src (not the folder name itself). Returns file count."""
    if zip_path.exists():
        zip_path.unlink()
    count = 0
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as zf:
        for file_path in sorted(src.rglob("*")):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(src)
            if not should_include(rel):
                continue
            zf.write(file_path, rel.as_posix())
            count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pack hub SPA folders into spa-*.zip release assets"
    )
    parser.add_argument(
        "--hub-dir",
        default=None,
        help="Hub directory containing SPA folders (default: parent of scripts/)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for spa-*.zip files (default: <hub-dir>/spa-release)",
    )
    args = parser.parse_args()

    hub = Path(args.hub_dir).resolve() if args.hub_dir else hub_dir_from_script()
    out_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else (hub / "spa-release")
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    packed = 0
    for folder in SPA_FOLDERS:
        src = hub / folder
        index = src / "index.html"
        if not index.is_file():
            print(f"Skip {folder}/ (no index.html)", file=sys.stderr)
            continue
        zip_path = out_dir / asset_name(folder)
        n = pack_folder(src, zip_path)
        print(f"Wrote {zip_path.name} ({n} files) from {folder}/")
        packed += 1

    if packed == 0:
        print(
            "Error: no SPA folders with index.html found under "
            f"{hub}. Sync clients first.",
            file=sys.stderr,
        )
        return 1
    print(f"Packed {packed} asset(s) into {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
