#!/usr/bin/env python3
"""Build sibling SPA clients and sync them into hub/ for Fly / Docker / make_zip.

Required: SlicerWebSub-js (worklist/reporting/classroom), SlicerLive, Viewers (OHIF).
Optional: slim, bellehumeur-website (warn and skip if missing).

Usage:
    cd WebSubInterface/hub
    python scripts/build_all_clients.py
    python scripts/build_all_clients.py --skip-build   # sync only
    python scripts/build_all_clients.py --skip-sync    # build only

Then:
    ./deploy-fly.sh mock
    # or: python make_zip.py --skip-build   # zip after a prior build_all
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

HUB_JS_CLIENTS_REPO = "SlicerWebSub-js"
HUB_JS_PACKAGES = ("worklist", "reporting", "classroom")
JS_DEST = {
    "worklist": "worklist-client",
    "reporting": "reporting-client",
    "classroom": "classroom-client",
}

# (dest under hub, discovery key)
CLIENT_SYNC_SPECS = (
    ("worklist-client", "worklist"),
    ("reporting-client", "reporting"),
    ("classroom-client", "classroom"),
    ("slicerlive", "slicerlive"),
    ("slicer-mirror", "slicermirror"),
    ("slim", "slim"),
    ("OHIF-client", "ohif"),
    ("website", "website"),
)
REQUIRED_SYNC_KEYS = frozenset(
    {"worklist", "reporting", "classroom", "slicerlive", "slicermirror", "ohif"}
)
OPTIONAL_SYNC_KEYS = frozenset({"slim", "website"})

DIST_PARTS_UNDER_REPO = {
    "worklist": (),
    "reporting": (),
    "classroom": (),
    "slicerlive": ("render", "demos", "ira"),
    "slicermirror": ("render", "demos", "slicer-mirror"),
    "slim": ("build",),
    "ohif": ("platform", "app", "dist"),
    "website": ("dist",),
}

_ESBUILD_DENO = ("run", "-A", "npm:esbuild@0.21.5")
_IRA_ENTRY = "render/demos/ira/ira-browser.ts"
_IRA_OUT = "render/demos/ira/ira.js"
_SLICER_MIRROR_ENTRY = "render/demos/slicer-mirror/slicer-mirror-browser.ts"
_SLICER_MIRROR_OUT = "render/demos/slicer-mirror/slicer-mirror.js"
_IDC_WORKER_SRC = "render/vendor/idc_tools/idc-worker.js"
_IDC_WORKER_DEST = "render/demos/ira/idc-worker.js"

SLICERLIVE_IRA_FILES = ("ira.html", "ira.js", "idc-worker.js")
SLICER_MIRROR_FILES = ("slicer-mirror.html", "slicer-mirror.js")

EXCLUDED_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "tools",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".ts", ".map"}
EXCLUDED_FILE_NAMES = {
    ".DS_Store",
    "package.json",
    "package-lock.json",
    ".gitignore",
    "LICENSE.txt",
    "requirements.txt",
}


def hub_dir_from_script() -> Path:
    return Path(__file__).resolve().parent.parent


def _npm() -> list[str]:
    return ["npm.cmd"] if os.name == "nt" else ["npm"]


def _pnpm() -> list[str]:
    return ["pnpm.cmd"] if os.name == "nt" else ["pnpm"]


def should_include(rel: Path) -> bool:
    if set(rel.parts) & EXCLUDED_DIR_NAMES:
        return False
    if any(part.endswith(".egg-info") for part in rel.parts):
        return False
    if rel.name in EXCLUDED_FILE_NAMES:
        return False
    if rel.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    if rel.suffix.lower() == ".md":
        return False
    return True


def sync_dist_tree(src: Path, dest: Path, *, ohif_mount_check: bool = False) -> int:
    index = src / "index.html"
    if not src.is_dir() or not index.is_file():
        raise FileNotFoundError(f"Source dist missing index.html: {src}")
    if ohif_mount_check and not ohif_index_is_cloud_mount(index):
        raise FileNotFoundError(
            f"OHIF index.html missing PUBLIC_URL=/ohif/ (got wrong build). "
            f"Rebuild with: cd Viewers/platform/app && pnpm run build:slicer-hub. "
            f"Index: {index}"
        )
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
        if not src_file.is_file():
            if name == "idc-worker.js":
                print(
                    f"Warning: {src_file} missing; IDC worker loads may fail",
                    file=sys.stderr,
                )
            continue
        shutil.copy2(src_file, dest / name)
        count += 1
    return count


def sync_slicer_mirror(src: Path, dest: Path) -> int:
    html = src / "slicer-mirror.html"
    js = src / "slicer-mirror.js"
    if not html.is_file() or not js.is_file():
        raise FileNotFoundError(f"slicer-mirror incomplete: {src}")
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(html, dest / "index.html")
    count = 1
    for name in SLICER_MIRROR_FILES:
        src_file = src / name
        if src_file.is_file():
            shutil.copy2(src_file, dest / name)
            count += 1
    return count


def ohif_index_is_cloud_mount(index: Path, expected: str = "/ohif/") -> bool:
    if not index.is_file():
        return False
    text = index.read_text(encoding="utf-8", errors="replace")
    needle = f"window.PUBLIC_URL = '{expected}'"
    if needle not in text:
        return False
    if 'src="/app.js"' in text or "src='/app.js'" in text:
        return False
    return True


def find_hub_js_root(search_from: Path) -> Path | None:
    for base in (search_from, *search_from.parents):
        root = base / HUB_JS_CLIENTS_REPO
        if (root / "package.json").is_file():
            return root.resolve()
    return None


def find_slicerlive_root(search_from: Path) -> Path | None:
    for base in (search_from, *search_from.parents):
        for candidate in (base / "pw46" / "SlicerLive", base / "SlicerLive"):
            if (candidate / "render" / "demos" / "ira" / "ira.html").is_file():
                return candidate.resolve()
    return None


def find_viewers_root(search_from: Path) -> Path | None:
    for base in (search_from, *search_from.parents):
        for candidate in (
            base / "Viewers",
            base / "hub-interface" / "Viewers",
            base / "ProjectWeek45" / "Viewers",
        ):
            if candidate.is_dir() and (candidate / "package.json").is_file():
                return candidate.resolve()
    return None


def find_slim_root(search_from: Path) -> Path | None:
    for base in (search_from, *search_from.parents):
        direct = base / "slim"
        if direct.is_dir() and (direct / "package.json").is_file():
            return direct.resolve()
    return None


def find_website_root(search_from: Path) -> Path | None:
    for base in (search_from, *search_from.parents):
        for candidate in (
            base / "cast-interface" / "bellehumeur-website",
            base / "bellehumeur-website",
        ):
            if candidate.is_dir() and (candidate / "build.py").is_file():
                return candidate.resolve()
    return None


def dist_for_key(search_from: Path, key: str, override: Path | None) -> Path:
    if override is not None:
        return override.resolve()
    if key in HUB_JS_PACKAGES:
        js = find_hub_js_root(search_from)
        if js is None:
            raise FileNotFoundError(
                f"Could not find {HUB_JS_CLIENTS_REPO} (searched from {search_from})"
            )
        return (js / "packages" / key).resolve()
    if key == "slicerlive":
        root = find_slicerlive_root(search_from)
        if root is None:
            raise FileNotFoundError("Could not find SlicerLive")
        return (root / Path(*DIST_PARTS_UNDER_REPO["slicerlive"])).resolve()
    if key == "slicermirror":
        root = find_slicerlive_root(search_from)
        if root is None:
            raise FileNotFoundError("Could not find SlicerLive slicer-mirror")
        return (root / Path(*DIST_PARTS_UNDER_REPO["slicermirror"])).resolve()
    if key == "ohif":
        root = find_viewers_root(search_from)
        if root is None:
            raise FileNotFoundError("Could not find Viewers repo")
        return (root / Path(*DIST_PARTS_UNDER_REPO["ohif"])).resolve()
    if key == "slim":
        root = find_slim_root(search_from)
        if root is None:
            raise FileNotFoundError("Could not find slim repo")
        return (root / Path(*DIST_PARTS_UNDER_REPO["slim"])).resolve()
    if key == "website":
        root = find_website_root(search_from)
        if root is None:
            raise FileNotFoundError("Could not find bellehumeur-website")
        return (root / Path(*DIST_PARTS_UNDER_REPO["website"])).resolve()
    raise ValueError(f"Unknown sync key: {key}")


def build_hub_js(js_root: Path) -> None:
    print(f"Building SlicerWebSub-js apps ({js_root}) …")
    lock = js_root / "package-lock.json"
    if lock.is_file():
        subprocess.run([*_npm(), "ci"], cwd=js_root, check=True)
    else:
        subprocess.run([*_npm(), "install"], cwd=js_root, check=True)
    subprocess.run([*_npm(), "run", "build:apps"], cwd=js_root, check=True)


def build_slicerlive(root: Path) -> None:
    print(f"Building SlicerLive demos ({root}) …")
    builds = (
        (_IRA_ENTRY, _IRA_OUT, "IRA"),
        (_SLICER_MIRROR_ENTRY, _SLICER_MIRROR_OUT, "slicer-mirror"),
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
        try:
            subprocess.run(cmd, cwd=root, check=True)
        except FileNotFoundError as err:
            raise RuntimeError(
                "deno not found; install Deno to build IRA / slicer-mirror"
            ) from err
        out_path = root / outfile
        if not out_path.is_file():
            raise RuntimeError(f"SlicerLive {label} build missing outfile: {out_path}")

    worker_dest = root / _IDC_WORKER_DEST
    if not worker_dest.is_file():
        worker_src = root / _IDC_WORKER_SRC
        if not worker_src.is_file():
            raise RuntimeError(
                f"SlicerLive idc-worker missing at {worker_dest} and {worker_src}"
            )
        worker_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(worker_src, worker_dest)
        print(f"Copied idc-worker.js -> {_IDC_WORKER_DEST}")
    print("Built SlicerLive IRA + slicer-mirror")


def build_ohif(viewers: Path) -> None:
    app = viewers / "platform" / "app"
    if not (app / "package.json").is_file():
        raise RuntimeError(f"OHIF app package.json missing: {app}")
    print(f"Building OHIF for /ohif/ ({app}) …")
    try:
        subprocess.run(
            [*_pnpm(), "run", "build:slicer-hub"],
            cwd=app,
            check=True,
        )
    except FileNotFoundError as err:
        raise RuntimeError("pnpm not found; install pnpm to build OHIF") from err
    index = app / "dist" / "index.html"
    if not ohif_index_is_cloud_mount(index):
        raise RuntimeError(f"OHIF build missing PUBLIC_URL=/ohif/: {index}")
    print("Built OHIF (PUBLIC_URL=/ohif/)")


def ensure_ohif_cloud_dist(viewers: Path) -> None:
    dist_index = viewers / "platform" / "app" / "dist" / "index.html"
    if ohif_index_is_cloud_mount(dist_index):
        return
    print(
        f"OHIF dist is not a /ohif/ build ({dist_index}); "
        "running pnpm run build:slicer-hub …"
    )
    build_ohif(viewers)


def build_slim(slim_root: Path) -> None:
    print(f"Building slim for /slim/ ({slim_root}) …")
    subprocess.run([*_pnpm(), "run", "build:cast"], cwd=slim_root, check=True)


def build_website(website_root: Path) -> None:
    print(f"Building bellehumeur-website ({website_root}) …")
    subprocess.run(
        [sys.executable, "build.py"],
        cwd=website_root,
        check=True,
    )


def run_builds(
    search_from: Path,
    *,
    js_root: Path | None,
    slicerlive_root: Path | None,
    viewers_root: Path | None,
    slim_root: Path | None,
    website_root: Path | None,
) -> None:
    js = js_root or find_hub_js_root(search_from)
    if js is None:
        raise RuntimeError(
            f"Could not find {HUB_JS_CLIENTS_REPO} (searched from {search_from})"
        )
    live = slicerlive_root or find_slicerlive_root(search_from)
    if live is None:
        raise RuntimeError(f"Could not find SlicerLive (searched from {search_from})")
    viewers = viewers_root or find_viewers_root(search_from)
    if viewers is None:
        raise RuntimeError(
            f"Could not find Viewers (searched from {search_from}). "
            "OHIF is required for build_all_clients."
        )

    build_hub_js(js)
    build_slicerlive(live)
    ensure_ohif_cloud_dist(viewers)

    slim = slim_root or find_slim_root(search_from)
    if slim is None:
        print("Warning: slim repo not found; skipping slim build", file=sys.stderr)
    else:
        try:
            build_slim(slim)
        except (RuntimeError, subprocess.CalledProcessError) as err:
            print(f"Warning: slim build failed ({err}); skipping", file=sys.stderr)

    website = website_root or find_website_root(search_from)
    if website is None:
        print(
            "Warning: bellehumeur-website not found; skipping website build",
            file=sys.stderr,
        )
    else:
        try:
            build_website(website)
        except (RuntimeError, subprocess.CalledProcessError) as err:
            print(f"Warning: website build failed ({err}); skipping", file=sys.stderr)


def run_sync(
    hub: Path,
    search_from: Path,
    *,
    js_root: Path | None,
    slicerlive_root: Path | None,
    viewers_root: Path | None,
    slim_root: Path | None,
    website_root: Path | None,
) -> None:
    overrides = {
        "worklist": (js_root / "packages" / "worklist") if js_root else None,
        "reporting": (js_root / "packages" / "reporting") if js_root else None,
        "classroom": (js_root / "packages" / "classroom") if js_root else None,
        "slicerlive": (
            (slicerlive_root / Path(*DIST_PARTS_UNDER_REPO["slicerlive"]))
            if slicerlive_root
            else None
        ),
        "slicermirror": (
            (slicerlive_root / Path(*DIST_PARTS_UNDER_REPO["slicermirror"]))
            if slicerlive_root
            else None
        ),
        "ohif": (
            (viewers_root / Path(*DIST_PARTS_UNDER_REPO["ohif"]))
            if viewers_root
            else None
        ),
        "slim": (
            (slim_root / Path(*DIST_PARTS_UNDER_REPO["slim"])) if slim_root else None
        ),
        "website": (
            (website_root / Path(*DIST_PARTS_UNDER_REPO["website"]))
            if website_root
            else None
        ),
    }

    for dest_name, key in CLIENT_SYNC_SPECS:
        dest = hub / dest_name
        try:
            src = dist_for_key(search_from, key, overrides.get(key))
            if key == "slicerlive":
                count = sync_slicerlive_ira(src, dest)
            elif key == "slicermirror":
                count = sync_slicer_mirror(src, dest)
            else:
                count = sync_dist_tree(
                    src, dest, ohif_mount_check=(key == "ohif")
                )
            print(f"Synced {src} -> {dest_name}/ ({count} files)")
        except FileNotFoundError as err:
            if key in OPTIONAL_SYNC_KEYS:
                print(f"Warning: {err}; skipping {dest_name}/", file=sys.stderr)
                continue
            raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build sibling SPA clients and sync into hub/ for Fly / Docker"
    )
    parser.add_argument(
        "--hub-dir",
        default=None,
        help="Hub directory (default: parent of scripts/)",
    )
    parser.add_argument("--js-root", default=None, help="SlicerWebSub-js root")
    parser.add_argument("--slicerlive-root", default=None, help="SlicerLive root")
    parser.add_argument("--viewers-root", default=None, help="Viewers (OHIF) root")
    parser.add_argument("--slim-root", default=None, help="slim repo root")
    parser.add_argument("--website-root", default=None, help="bellehumeur-website root")
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip builds; only sync existing dists into hub/",
    )
    parser.add_argument(
        "--skip-sync",
        action="store_true",
        help="Build only; do not copy into hub/",
    )
    args = parser.parse_args()

    hub = Path(args.hub_dir).resolve() if args.hub_dir else hub_dir_from_script()
    search_from = hub
    js_root = Path(args.js_root).resolve() if args.js_root else None
    live_root = Path(args.slicerlive_root).resolve() if args.slicerlive_root else None
    viewers_root = Path(args.viewers_root).resolve() if args.viewers_root else None
    slim_root = Path(args.slim_root).resolve() if args.slim_root else None
    website_root = Path(args.website_root).resolve() if args.website_root else None

    if args.skip_build and args.skip_sync:
        print("Nothing to do (--skip-build and --skip-sync)", file=sys.stderr)
        return 1

    try:
        if not args.skip_build:
            run_builds(
                search_from,
                js_root=js_root,
                slicerlive_root=live_root,
                viewers_root=viewers_root,
                slim_root=slim_root,
                website_root=website_root,
            )
        if not args.skip_sync:
            run_sync(
                hub,
                search_from,
                js_root=js_root,
                slicerlive_root=live_root,
                viewers_root=viewers_root,
                slim_root=slim_root,
                website_root=website_root,
            )
    except (RuntimeError, FileNotFoundError, subprocess.CalledProcessError) as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    print(f"SPA clients ready under {hub}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
