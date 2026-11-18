"""Resolve WebSubInterface module root and Python import paths."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def extension_root() -> Path:
    """Installed or source module directory (parent of Lib/)."""
    return Path(__file__).resolve().parent.parent


def repo_root() -> Path:
    """Module directory containing bundled hub/, python_client/, etc."""
    env = os.environ.get("HUB_REPO_ROOT", "").strip()
    if env:
        return Path(env).resolve()
    return extension_root()


def ensure_monorepo_import_paths() -> Path:
    """Append hub_client and image_display lib dirs to ``sys.path``.

    Call when opening the WebSubInterface module UI (or Connect/Start), not during
    Slicer scripted-module discovery. Does not add the module root (Slicer already
    exposes ``Lib``) and appends rather than prepending so other extensions are not
    shadowed.
    """
    root = repo_root()
    extras = (
        root / "python_client" / "src",
        root / "image_display" / "lib",
    )
    for path in extras:
        s = str(path)
        if path.is_dir() and s not in sys.path:
            sys.path.append(s)
    return root


def hub_dir() -> Path:
    return repo_root() / "hub"


def hub_script() -> Path:
    return hub_dir() / "hub.py"
