#!/usr/bin/env python3
"""Offline asserts: conference fan-out uses the same event and target filters as direct delivery."""

from __future__ import annotations

import sys
from pathlib import Path

_PYTHON_ROOT = Path(__file__).resolve().parents[1]
if str(_PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYTHON_ROOT))

from common.local_hub import HUBINTERFACE_ROOT, bootstrap_hubinterface_paths  # noqa: E402

_TOPIC = "USER-1"


def _sub(**overrides):
    sub = {
        "topic": _TOPIC,
        "channel": "websocket",
        "subscriber": "slicer-id-1",
        "events": "imagingstudy-open,scene-update",
        "actors": ["ID"],
        "client_info": {"productName": "3DSLICER-ID"},
    }
    sub.update(overrides)
    return sub


def main() -> int:
    bootstrap_hubinterface_paths()
    hub_root = HUBINTERFACE_ROOT / "hub"
    for path in (hub_root, hub_root / "Lib"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    from publish import _publish_delivers_to

    def delivers(sub, event="scene-update", actor="", product="", subscriber=""):
        return _publish_delivers_to(sub, _TOPIC, event, actor, product, subscriber)

    cases = [
        ("matching participant", delivers(_sub()), True),
        ("event not subscribed", delivers(_sub(), event="annotation-update"), False),
        ("wildcard events", delivers(_sub(events="*"), event="annotation-update"), True),
        ("other topic", _publish_delivers_to(_sub(topic="USER-2"), _TOPIC, "scene-update", "", "", ""), False),
        ("target.subscriber.name other", delivers(_sub(), subscriber="worklist-7"), False),
        ("target.subscriber.name match", delivers(_sub(), subscriber="SLICER-ID-1"), True),
        ("target.actor mismatch", delivers(_sub(), actor="WORKLIST_CLIENT"), False),
        ("target.actor match", delivers(_sub(), actor="ID"), True),
        ("target.product.name mismatch", delivers(_sub(), product="SLICER-MIRROR"), False),
        ("target.product.name match", delivers(_sub(), product="3DSLICER-ID"), True),
        ("target.product.name *", delivers(_sub(), product="*"), True),
    ]
    for label, got, want in cases:
        if got is not want:
            print(f"FAIL: {label}: delivers={got}, expected {want}")
            return 1

    print("OK publish delivery filters (direct + conference)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
