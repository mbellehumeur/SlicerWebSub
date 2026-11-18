#!/usr/bin/env python3
"""Offline asserts for proxy-download hop-by-hop redirect allowlisting."""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

_PYTHON_ROOT = Path(__file__).resolve().parents[1]
if str(_PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYTHON_ROOT))

from common.local_hub import HUBINTERFACE_ROOT, bootstrap_hubinterface_paths  # noqa: E402


def main() -> int:
    bootstrap_hubinterface_paths()
    idc_path = HUBINTERFACE_ROOT / "hub" / "Lib" / "routes" / "idc.py"
    src = idc_path.read_text(encoding="utf-8")

    if "allow_redirects=True" in src:
        print("FAIL: proxy-download still uses allow_redirects=True")
        return 1
    if "allow_redirects=False" not in src:
        print("FAIL: expected allow_redirects=False for hop checks")
        return 1
    for needle, err in (
        ("_PROXY_DOWNLOAD_MAX_REDIRECTS", "missing redirect depth cap"),
        ("_proxy_next_url", "missing _proxy_next_url"),
        ("_proxy_fetch_allowlisted", "missing _proxy_fetch_allowlisted"),
        ("Redirect host not allowlisted", "missing hop reject message"),
    ):
        if needle not in src:
            print(f"FAIL: {err}")
            return 1

    # Exercise the same host rules as idc._proxy_download_host_allowed /
    # _proxy_next_url without importing FastAPI route deps.
    allowed = {
        "github.com",
        "objects.githubusercontent.com",
        "release-assets.githubusercontent.com",
    }

    def host_ok(hostname: str) -> bool:
        host = str(hostname or "").strip().lower().rstrip(".")
        if not host:
            return False
        if host in allowed:
            return True
        return host.endswith(".githubusercontent.com")

    def next_url(current: str, location: str) -> str:
        joined = urljoin(current, location)
        parsed = urlparse(joined)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"bad scheme {parsed.scheme}")
        if not host_ok(parsed.hostname or ""):
            raise ValueError(f"Redirect host not allowlisted: {parsed.hostname}")
        return joined

    good = next_url(
        "https://github.com/org/repo/releases/download/v1/a.nii.gz",
        "https://objects.githubusercontent.com/github-production-release-asset/1",
    )
    if "objects.githubusercontent.com" not in good:
        print(f"FAIL: unexpected next url {good}")
        return 1
    try:
        next_url(
            "https://github.com/org/repo/releases/download/v1/a.nii.gz",
            "https://evil.example/steal",
        )
        print("FAIL: expected evil redirect to be rejected")
        return 1
    except ValueError as exc:
        if "not allowlisted" not in str(exc):
            print(f"FAIL: unexpected error: {exc}")
            return 1

    print("OK proxy-download hop redirect allowlist")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
