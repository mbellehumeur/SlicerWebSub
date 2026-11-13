"""Download hub SPA client trees from the SlicerWebSub GitHub Release."""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Floating release tag; assets are spa-<folder>.zip
SPA_CLIENTS_RELEASE = "spa-clients"
SPA_CLIENTS_RELEASE_BASE = (
    f"https://github.com/mbellehumeur/SlicerWebSub/releases/download/"
    f"{SPA_CLIENTS_RELEASE}"
)

# Light clients: default-checked in Qt when not yet installed.
DEFAULT_CHECKED_WHEN_MISSING = frozenset(
    {
        "worklist-client",
        "reporting-client",
        "classroom-client",
        "slicerlive",
        "slicer-mirror",
    }
)


@dataclass(frozen=True)
class SpaCatalogEntry:
    """One downloadable hub SPA mount."""

    folder: str
    label: str
    asset: str
    # Approximate spa-*.zip download size (update when packing spa-clients).
    size_bytes: int
    # One-line description for the Qt Hub SPA help text.
    summary: str

    @property
    def url(self) -> str:
        return f"{SPA_CLIENTS_RELEASE_BASE}/{self.asset}"


# Aligned with hub/Lib/static_spa.py SPA_CLIENTS (no marketing website/).
# size_bytes from local ZIP_DEFLATED packs of hub/<folder>/ (approx download cost).
SPA_DOWNLOAD_CATALOG: Tuple[SpaCatalogEntry, ...] = (
    SpaCatalogEntry(
        "worklist-client",
        "Worklist",
        "spa-worklist-client.zip",
        2_085_176,
        "Conference worklist and viewer launcher for hub sessions.",
    ),
    SpaCatalogEntry(
        "reporting-client",
        "Reporting",
        "spa-reporting-client.zip",
        99_083,
        "Structured reporting client for hub topics.",
    ),
    SpaCatalogEntry(
        "classroom-client",
        "Classroom",
        "spa-classroom-client.zip",
        1_040_309,
        "Teaching / classroom client for shared hub sessions.",
    ),
    SpaCatalogEntry(
        "slicerlive",
        "SlicerLive",
        "spa-slicerlive.zip",
        302_434,
        "SlicerLive IRA — WebGPU integrated reporting / live scene demo.",
    ),
    SpaCatalogEntry(
        "slicer-mirror",
        "Slicer mirror",
        "spa-slicer-mirror.zip",
        125_055,
        "Four-Up LiveScene stream from 3D Slicer Image Display.",
    ),
    SpaCatalogEntry(
        "slim",
        "Slim",
        "spa-slim.zip",
        2_676_322,
        "Slim DICOM viewer SPA.",
    ),
    SpaCatalogEntry(
        "OHIF-client",
        "OHIF",
        "spa-OHIF-client.zip",
        32_647_712,
        "OHIF v3 medical imaging viewer (largest download).",
    ),
)


def catalog_by_folder() -> dict:
    return {entry.folder: entry for entry in SPA_DOWNLOAD_CATALOG}


def is_installed(hub_dir: Path, folder: str) -> bool:
    """True when hub/<folder>/index.html exists."""
    return (Path(hub_dir) / folder / "index.html").is_file()


def default_checked(folder: str, installed: bool) -> bool:
    """Default checkbox: missing light SPAs on; installed and heavy SPAs off."""
    if installed:
        return False
    return folder in DEFAULT_CHECKED_WHEN_MISSING


def format_spa_size(nbytes: int) -> str:
    """Human-readable size for SPA zip labels (B / KB / MB / GB)."""
    n = max(0, int(nbytes))
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.0f} KB"
    if n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    return f"{n / (1024 * 1024 * 1024):.1f} GB"


def spa_checkbox_label(entry: SpaCatalogEntry) -> str:
    """Checkbox text: ``Label (1.2 MB)`` from the static catalog size."""
    if entry.size_bytes <= 0:
        return entry.label
    return f"{entry.label} ({format_spa_size(entry.size_bytes)})"


def spa_download_help_text() -> str:
    """Multi-line help under the Qt Download SPAs button."""
    lines = [
        "Downloads the selected browser clients from the spa-clients GitHub "
        "release into this hub folder. Restart the hub after install to serve them.",
        "",
    ]
    for entry in SPA_DOWNLOAD_CATALOG:
        lines.append(f"• {entry.label}: {entry.summary}")
    return "\n".join(lines)


def _download_url(url: str, dest: Path, *, timeout: float = 120.0) -> None:
    req = Request(url, headers={"User-Agent": "SlicerWebSub-spa-download/1.0"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            dest.write_bytes(resp.read())
    except HTTPError as err:
        if err.code == 404:
            raise FileNotFoundError(
                f"SPA asset not published yet (HTTP 404): {url}"
            ) from err
        raise RuntimeError(f"Download failed (HTTP {err.code}): {url}") from err
    except URLError as err:
        raise RuntimeError(f"Download failed: {url} ({err.reason})") from err


def _safe_extract_zip(zf: zipfile.ZipFile, dest_dir: Path) -> None:
    """Extract zip members under dest_dir; reject path traversal."""
    dest_dir = dest_dir.resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        if not name or name.endswith("/"):
            continue
        # Strip a single top-level folder if the zip wraps the SPA tree.
        parts = [p for p in name.split("/") if p and p != "."]
        if not parts:
            continue
        if ".." in parts:
            raise RuntimeError(f"Unsafe zip path: {info.filename}")
        target = (dest_dir / Path(*parts)).resolve()
        if not str(target).startswith(str(dest_dir)):
            raise RuntimeError(f"Unsafe zip path: {info.filename}")
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(info, "r") as src, open(target, "wb") as out:
            shutil.copyfileobj(src, out)


def _normalize_extracted_tree(dest_dir: Path) -> None:
    """If zip had a single top-level dir, flatten so index.html is at dest_dir."""
    index = dest_dir / "index.html"
    if index.is_file():
        return
    children = [p for p in dest_dir.iterdir() if p.name not in (".", "..")]
    if len(children) == 1 and children[0].is_dir():
        nested = children[0]
        if (nested / "index.html").is_file():
            for item in nested.iterdir():
                shutil.move(str(item), str(dest_dir / item.name))
            nested.rmdir()


def download_and_extract(
    hub_dir: Path,
    folder: str,
    asset: str | None = None,
    *,
    overwrite: bool = False,
    base_url: str | None = None,
) -> Path:
    """
    Download spa-<folder>.zip into hub/<folder>/.

    Raises FileNotFoundError when the release asset is missing (404).
    Raises FileExistsError when installed and overwrite is False.
    """
    hub_dir = Path(hub_dir)
    entry = catalog_by_folder().get(folder)
    if entry is None and not asset:
        raise ValueError(f"Unknown SPA folder: {folder}")
    asset_name = asset or (entry.asset if entry else f"spa-{folder}.zip")
    url_base = (base_url or SPA_CLIENTS_RELEASE_BASE).rstrip("/")
    url = f"{url_base}/{asset_name}"

    dest = hub_dir / folder
    if is_installed(hub_dir, folder) and not overwrite:
        raise FileExistsError(f"Already installed: {dest}")

    hub_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="spa-dl-") as tmp:
        zip_path = Path(tmp) / asset_name
        _download_url(url, zip_path)
        extract_root = Path(tmp) / "extract"
        extract_root.mkdir()
        with zipfile.ZipFile(zip_path, "r") as zf:
            _safe_extract_zip(zf, extract_root)
        _normalize_extracted_tree(extract_root)
        if not (extract_root / "index.html").is_file():
            raise RuntimeError(
                f"Downloaded {asset_name} but index.html is missing after extract"
            )
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(extract_root, dest)

    if not is_installed(hub_dir, folder):
        raise RuntimeError(f"Install incomplete: {dest / 'index.html'} missing")
    return dest


def download_selected(
    hub_dir: Path,
    folders: Sequence[str],
    *,
    overwrite_folders: Iterable[str] = (),
) -> List[Tuple[str, str]]:
    """
    Download each folder. Returns list of (folder, status) where status is
    'ok', or an error message.
    """
    overwrite_set = set(overwrite_folders)
    results: List[Tuple[str, str]] = []
    for folder in folders:
        try:
            download_and_extract(
                hub_dir,
                folder,
                overwrite=folder in overwrite_set or not is_installed(hub_dir, folder),
            )
            results.append((folder, "ok"))
        except Exception as exc:  # noqa: BLE001 — surface per-SPA errors to UI
            results.append((folder, str(exc)))
    return results
