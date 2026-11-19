"""Public base URL helpers for absolute links behind reverse proxies."""

from __future__ import annotations

import os

from fastapi import Request


def _env_public_base_url() -> str:
    override = os.environ.get("HUB_PUBLIC_BASE_URL", "").strip()
    return override.rstrip("/") if override else ""


def _request_public_base_url(request: Request) -> str:
    """Public HTTPS base URL for absolute links (Azure terminates TLS in front of uvicorn)."""
    explicit = _env_public_base_url()
    if explicit:
        return explicit

    forwarded_proto = (
        request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
    )
    forwarded_host = (
        request.headers.get("x-forwarded-host", "").split(",")[0].strip()
    )
    if not forwarded_host:
        forwarded_host = request.headers.get("host", "").strip()

    if forwarded_proto and forwarded_host:
        return f"{forwarded_proto}://{forwarded_host}".rstrip("/")

    base = str(request.base_url).rstrip("/")
    if base.startswith("http://") and (
        "azurewebsites.net" in base
        or request.headers.get("x-arr-ssl")
    ):
        return "https://" + base[len("http://") :]
    return base


def _oauth_public_base_url(request: Request) -> str:
    """Hub origin for OAuth redirects; OIDC mode never trusts request headers."""
    from oauth_tokens import HUB_AUTH_MODE

    if HUB_AUTH_MODE == "oidc":
        explicit = _env_public_base_url()
        if not explicit:
            raise RuntimeError("HUB_PUBLIC_BASE_URL is required in oidc mode")
        return explicit
    return _request_public_base_url(request)
