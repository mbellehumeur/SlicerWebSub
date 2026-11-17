#!/usr/bin/env python3
"""Offline asserts for admin access (HUB_ADMIN_TOKEN only; no hub required)."""

from __future__ import annotations

import sys
from pathlib import Path

_PYTHON_ROOT = Path(__file__).resolve().parents[1]
if str(_PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYTHON_ROOT))

from common.local_hub import HUBINTERFACE_ROOT, bootstrap_hubinterface_paths  # noqa: E402


def main() -> int:
    bootstrap_hubinterface_paths()
    hub_lib = HUBINTERFACE_ROOT / "hub" / "Lib"
    sys.path.insert(0, str(hub_lib))
    import oauth_tokens as ot

    # Local demo: neither admin token nor require-auth → open.
    ot.HUB_ADMIN_TOKEN = ""
    ot.HUB_REQUIRE_AUTH = False
    assert ot.validate_admin_access() == {}

    # Auth required but no admin token configured → fail closed.
    ot.HUB_REQUIRE_AUTH = True
    ot.HUB_ADMIN_TOKEN = ""
    try:
        ot.validate_admin_access(authorization_header="Bearer unused")
        print("FAIL: expected TokenValidationError when HUB_ADMIN_TOKEN unset")
        return 1
    except ot.TokenValidationError:
        pass

    # Matching admin token accepted; ordinary bearer rejected.
    ot.HUB_ADMIN_TOKEN = "secret-admin"
    assert ot.validate_admin_access(admin_token_header="secret-admin") == {
        "admin": True,
        "via": "admin_token",
    }
    assert ot.validate_admin_access(
        authorization_header="Bearer secret-admin"
    ) == {"admin": True, "via": "admin_token"}
    try:
        ot.validate_admin_access(authorization_header="Bearer not-the-admin")
        print("FAIL: ordinary bearer must not grant admin")
        return 1
    except ot.TokenValidationError:
        pass

    print("OK admin access gates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
