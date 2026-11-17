"""Ensure WebSubInterface Python packages in the Slicer environment."""

from __future__ import annotations

from pathlib import Path

import slicer
from slicer.i18n import tr as _

from .repo_paths import extension_root

# Fallback when slicer.packaging is unavailable (Slicer < 5.11).
_FALLBACK_PIP_PACKAGES = (
    ("fastapi", "fastapi"),
    ("uvicorn[standard]", "uvicorn"),
    ("python-multipart", "multipart"),
    ("aiohttp", "aiohttp"),
    ("psutil", "psutil"),
    ("PyJWT[crypto]", "jwt"),
)


class DepsDeclinedError(RuntimeError):
    """User declined installing missing packages into Slicer Python."""


def requirements_file() -> Path:
    return extension_root() / "Resources" / "requirements.txt"


def ensure_module_python_deps(*, requester: str = "WebSubInterface") -> None:
    """Install module requirements after user confirmation (action-time only).

    Prefer ``slicer.packaging.pip_ensure`` (Slicer 5.11+). Fall back to
    ``slicer.util.pip_install`` with an explicit confirm dialog on older builds.
    """
    req_path = requirements_file()
    packaging = getattr(slicer, "packaging", None)
    if packaging is not None and hasattr(packaging, "pip_ensure"):
        if not req_path.is_file():
            raise FileNotFoundError(f"Missing requirements file: {req_path}")
        reqs = packaging.load_requirements(str(req_path))
        if hasattr(packaging, "pip_check") and packaging.pip_check(reqs):
            return
        try:
            packaging.pip_ensure(reqs, requester=requester)
        except Exception as exc:
            # User cancel / install failure — surface as declined when check fails.
            if hasattr(packaging, "pip_check") and packaging.pip_check(reqs):
                return
            raise DepsDeclinedError(str(exc) or "dependency install declined") from exc
        if hasattr(packaging, "pip_check") and not packaging.pip_check(reqs):
            raise DepsDeclinedError("dependency install declined or incomplete")
        return

    _ensure_deps_legacy()


def _ensure_deps_legacy() -> None:
    """Pre-5.11 path: confirm then pip_install each missing package."""
    missing = []
    for pip_spec, import_name in _FALLBACK_PIP_PACKAGES:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pip_spec)
    if not missing:
        return
    package_list = "\n".join(f"  • {spec}" for spec in missing)
    if not slicer.util.confirmYesNoDisplay(
        _(
            "WebSubInterface needs packages that are not installed in this Slicer "
            "Python environment:\n\n{packages}\n\n"
            "Install them now with pip? This changes the Slicer Python site-packages."
        ).format(packages=package_list),
        windowTitle=_("Install WebSubInterface dependencies"),
    ):
        raise DepsDeclinedError("dependency install declined")
    for pip_spec in missing:
        slicer.util.pip_install(pip_spec)
    import importlib

    for _pip_spec, import_name in _FALLBACK_PIP_PACKAGES:
        importlib.import_module(import_name)
