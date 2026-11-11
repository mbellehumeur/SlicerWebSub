"""Shared hub OAuth presets for Image Display / conference (Hub module).

Mock hub OAuth does not validate client_secret. The value below is a public
placeholder (same as SlicerWebSub-js); do not commit real IdP secrets.

Worker products live in the sibling ``SlicerWebSub-workers`` repo and keep
their own copy of presets.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import urljoin, urlparse

# Public placeholder — not a credential (see module docstring).
_MOCK_CLIENT_SECRET = "client_secret_3d_Slicer"

HUBS: Dict[str, Dict[str, Any]] = {
    # Mock auth cloud hub (Fly bellehumeur-hub / apex).
    "SLICER-HUB-CLOUD": {
        "hub_endpoint": "https://bellehumeur-engineering.com/api/hub",
        "authorization_endpoint": "https://bellehumeur-engineering.com/oauth/login",
        "token_endpoint": "https://bellehumeur-engineering.com/oauth/token",
        "client_id": "130c3d9c-4157-4dd1-aa1d-slicer",
        "client_secret": _MOCK_CLIENT_SECRET,
        "lease": 999,
    },
    # OIDC cloud hub (Fly bellehumeur-hub-oidc).
    "SLICER-HUB-CLOUD-OIDC": {
        "hub_endpoint": "https://oidc.bellehumeur-engineering.com/api/hub",
        "authorization_endpoint": "https://oidc.bellehumeur-engineering.com/oauth/login",
        "token_endpoint": "https://oidc.bellehumeur-engineering.com/oauth/token",
        "client_id": "130c3d9c-4157-4dd1-aa1d-slicer",
        "client_secret": _MOCK_CLIENT_SECRET,
        "lease": 999,
    },
    "SLICER-HUB": {
        "hub_endpoint": "http://127.0.0.1:2018/api/hub",
        "authorization_endpoint": "http://127.0.0.1:2018/oauth/login",
        "token_endpoint": "http://127.0.0.1:2018/oauth/token",
        "client_id": "130c3d9c-4157-4dd1-aa1d-slicer",
        "client_secret": _MOCK_CLIENT_SECRET,
        "lease": 999,
    },
}

USER_NAME = "3dslicer-server"
DEFAULT_HUB_NAME = "SLICER-HUB"

# Main-thread queue poll while Image Display is active.
MAIN_QUEUE_TIMER_MS = 50

_HUB_NAME_ALIASES = {
    "VOLVIEW-HUB": "SLICER-HUB",
    "VOLVIEW-HUB-CLOUD": "SLICER-HUB-CLOUD",
}


def normalize_hub_name(name: str) -> str:
    """Map removed presets and invalid values to a configured Slicer hub."""
    key = str(name or "").strip()
    if not key:
        return DEFAULT_HUB_NAME
    key = _HUB_NAME_ALIASES.get(key, key)
    if key in HUBS:
        return key
    return DEFAULT_HUB_NAME


def hub_admin_url_for_name(hub_name: str) -> Optional[str]:
    """Admin portal URL for a configured hub (``hub_endpoint`` + ``admin``)."""
    hub_def = HUBS.get(hub_name)
    if not hub_def:
        return None
    hub_endpoint = str(hub_def.get("hub_endpoint", "")).strip()
    if not hub_endpoint:
        return None
    hub_base = hub_endpoint if hub_endpoint.endswith("/") else f"{hub_endpoint}/"
    admin_path = (
        "admin?theme=3dslicer"
        if hub_name in ("SLICER-HUB", "SLICER-HUB-CLOUD", "SLICER-HUB-CLOUD-OIDC")
        else "admin"
    )
    return urljoin(hub_base, admin_path)


def hub_worklist_url_for_name(hub_name: str) -> Optional[str]:
    """Worklist SPA URL for a configured hub (``{origin}/worklist-client/``)."""
    hub_def = HUBS.get(hub_name)
    if not hub_def:
        return None
    hub_endpoint = str(hub_def.get("hub_endpoint", "")).strip()
    if not hub_endpoint:
        return None
    parsed = urlparse(hub_endpoint)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}/worklist-client/"


def local_slicer_hub_admin_url(port: int) -> str:
    """Admin URL for the embedded local hub on ``port`` (3D Slicer theme)."""
    hub_base = f"http://127.0.0.1:{port}/api/hub/"
    return urljoin(hub_base, "admin?theme=3dslicer")
