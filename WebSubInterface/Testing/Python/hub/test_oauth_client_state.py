#!/usr/bin/env python3
"""Offline source asserts for native OIDC client_state round-trip."""

from __future__ import annotations

import sys
from pathlib import Path

_PYTHON_ROOT = Path(__file__).resolve().parents[1]
if str(_PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYTHON_ROOT))

from common.local_hub import HUBINTERFACE_ROOT, bootstrap_hubinterface_paths  # noqa: E402


def main() -> int:
    bootstrap_hubinterface_paths()
    oauth_path = HUBINTERFACE_ROOT / "hub" / "Lib" / "routes" / "oauth.py"
    src = oauth_path.read_text(encoding="utf-8")

    checks = [
        ("_normalize_client_state", "missing client_state normalizer"),
        ('pending["client_state"]', "login does not store client_state on pending"),
        ('redirect_params["client_state"]', "callback does not echo client_state"),
        ("client_state: str = \"\"", "oauth_login missing client_state query param"),
    ]
    for needle, err in checks:
        if needle not in src:
            print(f"FAIL: {err}")
            return 1

    print("OK oauth client_state round-trip source checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
