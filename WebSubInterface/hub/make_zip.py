#!/usr/bin/env python3
"""Create a deployment zip for Slicer WebSub (Azure zip deploy).

Build + sync of SPA mounts is delegated to ``scripts/build_all_clients.py``.
Fly.io / Docker ``:full`` only need the synced ``hub/`` folders — run
``python scripts/build_all_clients.py`` then ``./deploy-fly.sh``; no zip required.

Usage:
    python hub/make_zip.py
    python hub/make_zip.py --output slicer-hub.zip
    python hub/make_zip.py --skip-build    # sync via build_all, then zip
    python hub/make_zip.py --skip-sync     # zip hub/ as-is (no build_all)

See also: scripts/build_all_clients.py
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

EXCLUDED_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "tools",
    ".egg-info",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".ts", ".map"}
EXCLUDED_FILE_NAMES = {
    ".DS_Store",
    "slicer-hub.zip",
    "package.json",
    "package-lock.json",
    ".gitignore",
    "LICENSE.txt",
    # Local monorepo editable pin — Azure zip uses requirements-azure.txt instead.
    "requirements.txt",
}
EXCLUDED_DOC_SUFFIXES = {".md"}
AZURE_REQUIREMENTS_NAME = "requirements-azure.txt"

CLIENT_SYNC_SPECS = (
    ("worklist-client", "worklist"),
    ("reporting-client", "reporting"),
    ("classroom-client", "classroom"),
    ("slicerlive", "slicerlive"),
    ("hub-mirror", "hubmirror"),
    ("slim", "slim"),
    ("OHIF-client", "ohif"),
    ("website", "website"),
)

MOUNT_PATH_BY_DEST = {
    "worklist-client": "/worklist-client/",
    "reporting-client": "/reporting-client/",
    "classroom-client": "/classroom-client/",
    "slicerlive": "/slicerlive/",
    "hub-mirror": "/hub-mirror/",
    "slim": "/slim/",
    "OHIF-client": "/ohif/",
    "website": "/",
}


def should_include(path: Path) -> bool:
    parts = set(path.parts)
    if parts & EXCLUDED_DIR_NAMES:
        return False
    if any(part.endswith(".egg-info") for part in path.parts):
        return False
    if path.name in EXCLUDED_FILE_NAMES:
        return False
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    if path.suffix.lower() in EXCLUDED_DOC_SUFFIXES:
        return False
    return True


def ohif_index_is_cloud_mount(index: Path, expected: str = "/ohif/") -> bool:
    """True when index.html was built for the hub /ohif/ mount (not site root)."""
    if not index.is_file():
        return False
    text = index.read_text(encoding="utf-8", errors="replace")
    needle = f"window.PUBLIC_URL = '{expected}'"
    if needle not in text:
        return False
    if 'src="/app.js"' in text or "src='/app.js'" in text:
        return False
    return True


def assert_ohif_public_url(index: Path, expected: str = "/ohif/") -> None:
    if ohif_index_is_cloud_mount(index, expected):
        return
    needle = f"window.PUBLIC_URL = '{expected}'"
    raise FileNotFoundError(
        f"OHIF index.html missing {needle!r} (got wrong PUBLIC_URL). "
        f"Rebuild with: python scripts/build_all_clients.py "
        f"(or cd Viewers/platform/app && pnpm run build:slicer-hub). "
        f"Index: {index}"
    )


def find_python_client(script_dir: Path) -> Path | None:
    """Locate WebSubInterface/python_client next to hub."""
    sibling = (script_dir.parent / "python_client").resolve()
    if sibling.is_dir() and (sibling / "src" / "hub_client").is_dir():
        return sibling
    for base in script_dir.parents:
        candidate = base / "WebSubInterface" / "python_client"
        if candidate.is_dir() and (candidate / "src" / "hub_client").is_dir():
            return candidate.resolve()
    return None


def add_tree_to_zip(
    zf: ZipFile,
    src_root: Path,
    arc_prefix: str,
) -> int:
    """Add files under src_root into the zip under arc_prefix/. Returns file count."""
    count = 0
    for file_path in sorted(src_root.rglob("*")):
        if not file_path.is_file():
            continue
        rel = file_path.relative_to(src_root)
        if not should_include(rel):
            continue
        arcname = f"{arc_prefix.rstrip('/')}/{rel.as_posix()}"
        zf.write(file_path, arcname)
        count += 1
    return count


def build_zip(source_dir: Path, output_zip: Path) -> tuple[int, dict[str, int]]:
    file_count = 0
    client_counts: dict[str, int] = {name: 0 for name, _ in CLIENT_SYNC_SPECS}
    azure_req = source_dir / AZURE_REQUIREMENTS_NAME
    with ZipFile(output_zip, "w", ZIP_DEFLATED) as zf:
        if azure_req.is_file():
            zf.write(azure_req, "requirements.txt")
            file_count += 1
            print(
                f"Packaged {AZURE_REQUIREMENTS_NAME} as requirements.txt "
                "(omitted -e ../python_client)"
            )
        else:
            print(
                f"Warning: {AZURE_REQUIREMENTS_NAME} missing; "
                "zip will not include requirements.txt",
                file=sys.stderr,
            )

        for file_path in sorted(source_dir.rglob("*")):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(source_dir)
            if not should_include(rel):
                continue
            if rel.as_posix() == AZURE_REQUIREMENTS_NAME:
                continue
            # Do not ship packed release assets inside the Azure zip.
            if rel.parts and rel.parts[0] == "spa-release":
                continue
            if rel.parts and rel.parts[0] == "scripts":
                continue
            arcname = rel.as_posix()
            zf.write(file_path, arcname)
            file_count += 1
            for client_name, _ in CLIENT_SYNC_SPECS:
                prefix = f"{client_name}/"
                if arcname.startswith(prefix):
                    client_counts[client_name] += 1
                    break

        py_client = find_python_client(source_dir)
        if py_client is not None:
            n = add_tree_to_zip(zf, py_client, "python_client")
            file_count += n
            print(f"Packaged python_client/ ({n} files) from {py_client}")
            client_counts["python_client"] = n
        else:
            print(
                "Warning: python_client not found; hub may fail to import hub_client",
                file=sys.stderr,
            )

    return file_count, client_counts


def run_build_all_clients(
    hub_dir: Path,
    *,
    skip_build: bool,
    skip_sync: bool,
) -> int:
    """Invoke scripts/build_all_clients.py; return its exit code."""
    script = hub_dir / "scripts" / "build_all_clients.py"
    if not script.is_file():
        print(f"Error: missing {script}", file=sys.stderr)
        return 1
    cmd = [
        sys.executable,
        str(script),
        "--hub-dir",
        str(hub_dir),
    ]
    if skip_build:
        cmd.append("--skip-build")
    if skip_sync:
        cmd.append("--skip-sync")
    print(f"Running {' '.join(cmd)} …")
    completed = subprocess.run(cmd, check=False)
    return int(completed.returncode)


def main() -> int:
    script_dir = Path(__file__).resolve().parent

    parser = argparse.ArgumentParser(
        description=(
            "Sync hub SPA clients via build_all_clients.py and create "
            "hub zip deployment package"
        )
    )
    parser.add_argument(
        "--output",
        default=str(script_dir / "slicer-hub.zip"),
        help="Output zip path (default: hub/slicer-hub.zip)",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Pass --skip-build to build_all_clients (sync existing dists only)",
    )
    parser.add_argument(
        "--skip-sync",
        action="store_true",
        help="Skip build_all_clients; zip hub/ as-is",
    )
    args = parser.parse_args()

    output_zip = Path(args.output).resolve()
    output_zip.parent.mkdir(parents=True, exist_ok=True)

    if not args.skip_sync:
        rc = run_build_all_clients(
            script_dir,
            skip_build=args.skip_build,
            skip_sync=False,
        )
        if rc != 0:
            return rc

    for dest_name, _ in CLIENT_SYNC_SPECS:
        index = script_dir / dest_name / "index.html"
        if not index.is_file():
            mount = MOUNT_PATH_BY_DEST.get(dest_name, f"/{dest_name}/")
            print(
                f"Warning: {dest_name}/index.html not found; "
                f"hub will not serve {mount}",
                file=sys.stderr,
            )
            continue
        if dest_name == "OHIF-client":
            try:
                assert_ohif_public_url(index)
            except FileNotFoundError as err:
                print(f"Error: {err}", file=sys.stderr)
                return 1

    if output_zip.exists():
        output_zip.unlink()

    file_count, client_counts = build_zip(script_dir, output_zip)
    summary_parts = [
        f"{name}={client_counts.get(name, 0)}" for name, _ in CLIENT_SYNC_SPECS
    ]
    if "python_client" in client_counts:
        summary_parts.append(f"python_client={client_counts['python_client']}")
    print(f"Created {output_zip} ({file_count} files; {', '.join(summary_parts)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
