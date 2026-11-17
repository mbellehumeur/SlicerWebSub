#!/usr/bin/env python3
"""Offline asserts for conference membership helpers (no live hub)."""

from __future__ import annotations

import sys
from pathlib import Path

_PYTHON_ROOT = Path(__file__).resolve().parents[1]
if str(_PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYTHON_ROOT))

from common.local_hub import HUBINTERFACE_ROOT, bootstrap_hubinterface_paths  # noqa: E402


def main() -> int:
    bootstrap_hubinterface_paths()
    hub_dir = HUBINTERFACE_ROOT / "hub"
    hub_lib = hub_dir / "Lib"
    # Prefer hub/Lib imports without loading routes package __init__ (idc deps).
    sys.path.insert(0, str(hub_dir))
    sys.path.insert(0, str(hub_lib))

    import importlib.util

    import oauth_tokens as ot
    import http_util
    from http_util import _enforce_topic_match

    conf_path = hub_lib / "routes" / "conference.py"
    spec = importlib.util.spec_from_file_location(
        "hub_conference_routes_under_test", conf_path
    )
    assert spec and spec.loader
    conf_routes = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(conf_routes)

    def _set_auth_mode(mode: str) -> None:
        ot.HUB_AUTH_MODE = mode
        http_util.HUB_AUTH_MODE = mode
        conf_routes.HUB_AUTH_MODE = mode

    # Mock mode: topic match is a no-op.
    _set_auth_mode("mock")
    _enforce_topic_match({"topic": "alice"}, "bob")
    conf_routes._enforce_conference_actor({"topic": "alice"}, "bob")

    # OIDC: join/create-style match must equal JWT topic.
    _set_auth_mode("oidc")
    try:
        _enforce_topic_match({"topic": "alice@example.com"}, "bob@example.com")
        print("FAIL: expected topic mismatch 403")
        return 1
    except Exception as exc:
        status = getattr(exc, "status_code", None)
        if status != 403:
            print(f"FAIL: expected HTTP 403, got {exc!r}")
            return 1

    _enforce_topic_match({"topic": "alice@example.com"}, "alice@example.com")
    conf_routes._enforce_conference_actor(
        {"topic": "alice@example.com"},
        "host@example.com",
        "alice@example.com",
    )
    try:
        conf_routes._enforce_conference_actor(
            {"topic": "attacker@example.com"},
            "host@example.com",
            "victim@example.com",
        )
        print("FAIL: expected actor mismatch 403")
        return 1
    except Exception as exc:
        status = getattr(exc, "status_code", None)
        if status != 403:
            print(f"FAIL: expected HTTP 403, got {exc!r}")
            return 1

    # Create may notify invitees but membership stays empty until /join.
    src = conf_path.read_text(encoding="utf-8")
    if '"topics": []' not in src and "'topics': []" not in src:
        print("FAIL: create does not start with empty membership topics")
        return 1
    if "invite_topics" not in src or "notify_topics" not in src:
        print("FAIL: create missing invite notify fan-out")
        return 1

    print("OK conference membership topic gates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
