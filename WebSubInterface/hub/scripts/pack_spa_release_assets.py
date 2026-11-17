#!/usr/bin/env python3
"""Pack hub SPA folders into spa-clients.zip for the spa-clients release.

Expects trees already synced under hub/ (index.html present). Does not build
or sync from sibling repos — use prepare_spa_release.py or make_zip.py first.

The zip has top-level SPA folder names so unpacking into hub/ installs mounts:
    worklist-client/index.html, OHIF-client/..., …

Usage (from anywhere):
    python WebSubInterface/hub/scripts/pack_spa_release_assets.py
    python WebSubInterface/hub/scripts/pack_spa_release_assets.py --output-dir dist/spa
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

# Keep in sync with hub/Lib/static_spa.py SPA_CLIENTS folders.
SPA_FOLDERS = (
    "worklist-client",
    "reporting-client",
    "classroom-client",
    "slicerlive",
    "slicer-mirror",
    "slim",
    "OHIF-client",
)

COMBINED_ASSET_NAME = "spa-clients.zip"

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


def pack_combined(hub: Path, zip_path: Path, folders: tuple[str, ...]) -> tuple[int, list[str]]:
    """Zip SPA trees with folder names at zip root. Returns (file count, packed folders)."""
    if zip_path.exists():
        zip_path.unlink()
    count = 0
    packed: list[str] = []
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as zf:
        for folder in folders:
            src = hub / folder
            if not (src / "index.html").is_file():
                print(f"Skip {folder}/ (no index.html)", file=sys.stderr)
                continue
            packed.append(folder)
            for file_path in sorted(src.rglob("*")):
                if not file_path.is_file():
                    continue
                rel = file_path.relative_to(src)
                if not should_include(rel):
                    continue
                arcname = f"{folder}/{rel.as_posix()}"
                zf.write(file_path, arcname)
                count += 1
    return count, packed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pack hub SPA folders into spa-clients.zip"
    )
    parser.add_argument(
        "--hub-dir",
        default=None,
        help="Hub directory containing SPA folders (default: parent of scripts/)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for spa-clients.zip (default: <hub-dir>/spa-release)",
    )
    args = parser.parse_args()

    hub = Path(args.hub_dir).resolve() if args.hub_dir else hub_dir_from_script()
    out_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else (hub / "spa-release")
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    zip_path = out_dir / COMBINED_ASSET_NAME
    n, packed = pack_combined(hub, zip_path, SPA_FOLDERS)
    if not packed:
        if zip_path.exists():
            zip_path.unlink()
        print(
            "Error: no SPA folders with index.html found under "
            f"{hub}. Sync clients first.",
            file=sys.stderr,
        )
        return 1

    print(f"Wrote {zip_path.name} ({n} files) from: {', '.join(packed)}")
    print(f"Packed into {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
