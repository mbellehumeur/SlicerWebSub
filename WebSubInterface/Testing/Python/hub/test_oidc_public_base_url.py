#!/usr/bin/env python3
"""Offline asserts: OIDC requires HUB_PUBLIC_BASE_URL and ignores forwarded host headers."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_PYTHON_ROOT = Path(__file__).resolve().parents[1]
if str(_PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYTHON_ROOT))

from common.local_hub import HUBINTERFACE_ROOT, bootstrap_hubinterface_paths  # noqa: E402

_PUBLIC_BASE = "https://hub.example.com"
_EVIL_HOST = "evil.example"


def _forged_request():
    from starlette.requests import Request

    headers = [
        (b"host", _EVIL_HOST.encode()),
        (b"x-forwarded-host", _EVIL_HOST.encode()),
        (b"x-forwarded-proto", b"https"),
    ]
    scope = {
        "type": "http",
        "method": "GET",
        "scheme": "http",
        "server": ("127.0.0.1", 2018),
        "path": "/oauth/login",
        "query_string": b"",
        "headers": headers,
    }
    return Request(scope)


def main() -> int:
    bootstrap_hubinterface_paths()
    hub_root = HUBINTERFACE_ROOT / "hub"
    for path in (hub_root, hub_root / "Lib"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))

    os.environ.update(
        {
            "HUB_AUTH_MODE": "oidc",
            "HUB_OIDC_ISSUER": "https://idp.example.com",
            "HUB_OIDC_CLIENT_ID": "client",
            "HUB_OIDC_CLIENT_SECRET": "secret",
            "HUB_JWT_SECRET": "test-secret-not-the-default-0123456789",
        }
    )
    os.environ.pop("HUB_PUBLIC_BASE_URL", None)
    os.environ.pop("HUB_OIDC_REDIRECT_URI", None)
    os.environ.pop("HUB_OIDC_RETURN_ORIGINS", None)

    import oauth_tokens

    try:
        oauth_tokens.assert_oidc_runtime_config()
    except RuntimeError as exc:
        if "HUB_PUBLIC_BASE_URL" not in str(exc):
            print(f"FAIL: unexpected startup error: {exc}")
            return 1
    else:
        print("FAIL: oidc startup accepted missing HUB_PUBLIC_BASE_URL")
        return 1

    os.environ["HUB_PUBLIC_BASE_URL"] = "hub.example.com"
    try:
        oauth_tokens.assert_oidc_runtime_config()
    except RuntimeError:
        pass
    else:
        print("FAIL: oidc startup accepted non-absolute HUB_PUBLIC_BASE_URL")
        return 1

    os.environ["HUB_PUBLIC_BASE_URL"] = _PUBLIC_BASE
    oauth_tokens.assert_oidc_runtime_config()

    from routes import oauth as oauth_routes

    request = _forged_request()
    origins = oauth_routes._allowed_return_origins(request)
    if any(_EVIL_HOST in origin for origin in origins):
        print(f"FAIL: forged host in allowed return origins: {origins}")
        return 1
    if _PUBLIC_BASE not in origins:
        print(f"FAIL: configured origin missing from allowed origins: {origins}")
        return 1

    for raw in ("", "/worklist-client/", f"https://{_EVIL_HOST}/steal"):
        resolved = oauth_routes._safe_return_to(raw, request)
        if _EVIL_HOST in resolved or not resolved.startswith(_PUBLIC_BASE):
            print(f"FAIL: return_to {raw!r} resolved to {resolved!r}")
            return 1

    redirect_uri = oauth_routes._oidc_redirect_uri(request)
    if redirect_uri != f"{_PUBLIC_BASE}/oauth/callback":
        print(f"FAIL: redirect_uri derived from request: {redirect_uri!r}")
        return 1

    print("OK oidc public base url ignores forwarded host headers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
