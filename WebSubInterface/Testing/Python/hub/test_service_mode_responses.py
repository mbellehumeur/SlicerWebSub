#!/usr/bin/env python3
"""Offline asserts: audit-log responses keep payloads only when HUB_SERVICE_MODE is on."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

_PYTHON_ROOT = Path(__file__).resolve().parents[1]
if str(_PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYTHON_ROOT))

from common.local_hub import HUBINTERFACE_ROOT, bootstrap_hubinterface_paths  # noqa: E402

_RESPONSES = [
    {
        "id": "r1",
        "subscriber": "slicer-id-1",
        "actor": "ImageDisplay",
        "productName": "3D Slicer",
        "data": {"studies": [{"patientName": "DOE^JANE"}]},
    }
]


def _load_hub_request(service_mode: str | None):
    if service_mode is None:
        os.environ.pop("HUB_SERVICE_MODE", None)
    else:
        os.environ["HUB_SERVICE_MODE"] = service_mode
    import env
    import hub_request

    importlib.reload(env)
    return importlib.reload(hub_request)


def main() -> int:
    bootstrap_hubinterface_paths()
    hub_root = HUBINTERFACE_ROOT / "hub"
    for path in (hub_root, hub_root / "Lib"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))

    for value in (None, "false"):
        hub_request = _load_hub_request(value)
        audited = hub_request._audit_responses(_RESPONSES)
        if len(audited) != 1:
            print(f"FAIL: HUB_SERVICE_MODE={value!r} changed response count")
            return 1
        entry = audited[0]
        if entry.get("data") is not None or entry.get("dataOmitted") is not True:
            print(f"FAIL: HUB_SERVICE_MODE={value!r} kept payload: {entry}")
            return 1
        if entry.get("subscriber") != "slicer-id-1" or entry.get("id") != "r1":
            print(f"FAIL: HUB_SERVICE_MODE={value!r} dropped identity fields: {entry}")
            return 1
        if _RESPONSES[0]["data"] is None:
            print("FAIL: redaction mutated the collected responses")
            return 1

    hub_request = _load_hub_request("true")
    audited = hub_request._audit_responses(_RESPONSES)
    if audited != _RESPONSES or "dataOmitted" in audited[0]:
        print(f"FAIL: HUB_SERVICE_MODE=true altered responses: {audited}")
        return 1

    print("OK service mode controls audit response payloads")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
