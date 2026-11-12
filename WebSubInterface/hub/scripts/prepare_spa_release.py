#!/usr/bin/env python3
"""Build and sync hub SPA trees for the spa-clients GitHub Release.

Tracked alternative to gitignored make_zip.py for CI. Syncs into hub/:

  worklist-client, reporting-client, classroom-client  <- SlicerWebSub-js
  slicerlive, hub-mirror                               <- SlicerLive demos
  OHIF-client                                          <- Viewers (optional)
  slim                                                 <- slim (optional)

Usage:
    python prepare_spa_release.py \\
      --js-root ../SlicerWebSub-js \\
      --slicerlive-root ../SlicerLive

    python prepare_spa_release.py ... --include-ohif --viewers-root ../Viewers
    python prepare_spa_release.py ... --include-slim --slim-root ../slim
    python prepare_spa_release.py ... --skip-build
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

HUB_JS_PACKAGES = ("worklist", "reporting", "classroom")
JS_DEST = {
    "worklist": "worklist-client",
    "reporting": "reporting-client",
    "classroom": "classroom-client",
}

_ESBUILD_DENO = ("run", "-A", "npm:esbuild@0.21.5")
_IRA_ENTRY = "render/demos/ira/ira-browser.ts"
_IRA_OUT = "render/demos/ira/ira.js"
_HUB_MIRROR_ENTRY = "render/demos/hub-mirror/hub-mirror-browser.ts"
_HUB_MIRROR_OUT = "render/demos/hub-mirror/hub-mirror.js"
_IDC_WORKER_SRC = "render/vendor/idc_tools/idc-worker.js"
_IDC_WORKER_DEST = "render/demos/ira/idc-worker.js"

SLICERLIVE_IRA_FILES = ("ira.html", "ira.js", "idc-worker.js")
HUB_MIRROR_FILES = ("hub-mirror.html", "hub-mirror.js")

EXCLUDED_DIR_NAMES = {".git", "__pycache__", "node_modules"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".ts", ".map"}
EXCLUDED_FILE_NAMES = {".DS_Store", "package.json", "package-lock.json"}


def hub_dir_from_script() -> Path:
    return Path(__file__).resolve().parent.parent


def _npm() -> list[str]:
    return ["npm.cmd"] if os.name == "nt" else ["npm"]


def _pnpm() -> list[str]:
    return ["pnpm.cmd"] if os.name == "nt" else ["pnpm"]


def should_include(rel: Path) -> bool:
    if set(rel.parts) & EXCLUDED_DIR_NAMES:
        return False
    if rel.name in EXCLUDED_FILE_NAMES:
        return False
    if rel.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    if rel.suffix.lower() == ".md":
        return False
    return True


def sync_dist_tree(src: Path, dest: Path) -> int:
    index = src / "index.html"
    if not src.is_dir() or not index.is_file():
        raise FileNotFoundError(f"Source dist missing index.html: {src}")
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    count = 0
    for file_path in src.rglob("*"):
        if not file_path.is_file():
            continue
        rel = file_path.relative_to(src)
        if not should_include(rel):
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, target)
        count += 1
    return count


def sync_slicerlive_ira(src: Path, dest: Path) -> int:
    ira_html = src / "ira.html"
    ira_js = src / "ira.js"
    if not ira_html.is_file() or not ira_js.is_file():
        raise FileNotFoundError(f"SlicerLive IRA incomplete: {src}")
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ira_html, dest / "index.html")
    count = 1
    for name in SLICERLIVE_IRA_FILES:
        src_file = src / name
        if src_file.is_file():
            shutil.copy2(src_file, dest / name)
            count += 1
    return count


def sync_hub_mirror(src: Path, dest: Path) -> int:
    html = src / "hub-mirror.html"
    js = src / "hub-mirror.js"
    if not html.is_file() or not js.is_file():
        raise FileNotFoundError(f"hub-mirror incomplete: {src}")
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(html, dest / "index.html")
    count = 1
    for name in HUB_MIRROR_FILES:
        src_file = src / name
        if src_file.is_file():
            shutil.copy2(src_file, dest / name)
            count += 1
    return count


def build_hub_js(js_root: Path) -> None:
    print(f"Building SlicerWebSub-js apps ({js_root}) …")
    subprocess.run([*_npm(), "ci"], cwd=js_root, check=True)
    subprocess.run([*_npm(), "run", "build:apps"], cwd=js_root, check=True)


def build_slicerlive(root: Path) -> None:
    print(f"Building SlicerLive demos ({root}) …")
    builds = (
        (_IRA_ENTRY, _IRA_OUT, "IRA"),
        (_HUB_MIRROR_ENTRY, _HUB_MIRROR_OUT, "hub-mirror"),
    )
    for entry, outfile, label in builds:
        entry_path = root / entry
        if not entry_path.is_file():
            raise RuntimeError(f"SlicerLive {label} entry missing: {entry_path}")
        cmd = [
            "deno",
            *_ESBUILD_DENO,
            entry,
            "--bundle",
            "--format=esm",
            f"--outfile={outfile}",
        ]
        subprocess.run(cmd, cwd=root, check=True)
    worker_dest = root / _IDC_WORKER_DEST
    if not worker_dest.is_file():
        worker_src = root / _IDC_WORKER_SRC
        if not worker_src.is_file():
            raise RuntimeError(f"idc-worker missing: {worker_src}")
        worker_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(worker_src, worker_dest)


def ohif_index_is_cloud_mount(index: Path) -> bool:
    if not index.is_file():
        return False
    text = index.read_text(encoding="utf-8", errors="replace")
    if "window.PUBLIC_URL = '/ohif/'" not in text:
        return False
    if 'src="/app.js"' in text or "src='/app.js'" in text:
        return False
    return True


def build_ohif(viewers: Path) -> None:
    app = viewers / "platform" / "app"
    print(f"Building OHIF for /ohif/ ({app}) …")
    subprocess.run([*_pnpm(), "install", "--frozen-lockfile"], cwd=viewers, check=True)
    subprocess.run([*_pnpm(), "run", "build:slicer-hub"], cwd=app, check=True)
    index = app / "dist" / "index.html"
    if not ohif_index_is_cloud_mount(index):
        raise RuntimeError(f"OHIF build missing PUBLIC_URL=/ohif/: {index}")


def build_slim(slim_root: Path) -> None:
    print(f"Building slim for /slim/ ({slim_root}) …")
    subprocess.run([*_pnpm(), "install", "--frozen-lockfile"], cwd=slim_root, check=True)
    subprocess.run([*_pnpm(), "run", "build:cast"], cwd=slim_root, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare hub SPA trees for release")
    parser.add_argument("--hub-dir", default=None)
    parser.add_argument("--js-root", required=True, help="SlicerWebSub-js repo root")
    parser.add_argument("--slicerlive-root", required=True, help="SlicerLive repo root")
    parser.add_argument("--viewers-root", default=None, help="OHIF Viewers repo root")
    parser.add_argument("--slim-root", default=None, help="slim repo root")
    parser.add_argument("--include-ohif", action="store_true")
    parser.add_argument("--include-slim", action="store_true")
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()

    hub = Path(args.hub_dir).resolve() if args.hub_dir else hub_dir_from_script()
    js_root = Path(args.js_root).resolve()
    live_root = Path(args.slicerlive_root).resolve()

    if not args.skip_build:
        try:
            build_hub_js(js_root)
            build_slicerlive(live_root)
            if args.include_ohif:
                if not args.viewers_root:
                    print("--include-ohif requires --viewers-root", file=sys.stderr)
                    return 1
                build_ohif(Path(args.viewers_root).resolve())
            if args.include_slim:
                if not args.slim_root:
                    print("--include-slim requires --slim-root", file=sys.stderr)
                    return 1
                build_slim(Path(args.slim_root).resolve())
        except (RuntimeError, FileNotFoundError, subprocess.CalledProcessError) as err:
            print(f"Error: {err}", file=sys.stderr)
            return 1

    try:
        for pkg in HUB_JS_PACKAGES:
            src = js_root / "packages" / pkg
            dest = hub / JS_DEST[pkg]
            n = sync_dist_tree(src, dest)
            print(f"Synced {src} -> {dest.name}/ ({n} files)")

        ira_src = live_root / "render" / "demos" / "ira"
        n = sync_slicerlive_ira(ira_src, hub / "slicerlive")
        print(f"Synced IRA -> slicerlive/ ({n} files)")

        mirror_src = live_root / "render" / "demos" / "hub-mirror"
        n = sync_hub_mirror(mirror_src, hub / "hub-mirror")
        print(f"Synced hub-mirror -> hub-mirror/ ({n} files)")

        if args.include_ohif:
            viewers = Path(args.viewers_root).resolve()
            ohif_dist = viewers / "platform" / "app" / "dist"
            if not ohif_index_is_cloud_mount(ohif_dist / "index.html"):
                raise FileNotFoundError(
                    f"OHIF dist is not a /ohif/ build: {ohif_dist / 'index.html'}"
                )
            n = sync_dist_tree(ohif_dist, hub / "OHIF-client")
            print(f"Synced OHIF -> OHIF-client/ ({n} files)")

        if args.include_slim:
            slim_build = Path(args.slim_root).resolve() / "build"
            n = sync_dist_tree(slim_build, hub / "slim")
            print(f"Synced slim -> slim/ ({n} files)")
    except FileNotFoundError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    print(f"SPA trees ready under {hub}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
