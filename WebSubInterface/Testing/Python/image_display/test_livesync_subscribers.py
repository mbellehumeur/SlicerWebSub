#!/usr/bin/env python3
"""Offline asserts: LiveSync subscribers share one Hub sink peer without narrowing each other."""

from __future__ import annotations

import sys
from pathlib import Path

_PYTHON_ROOT = Path(__file__).resolve().parents[1]
if str(_PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYTHON_ROOT))

from common.local_hub import bootstrap_hubinterface_paths  # noqa: E402

MIRROR_TYPES = ["camera", "view", "segmentation", "image", "mesh"]
IRA_TYPES = ["camera", "view", "segmentation"]


class _FakePeer:
    def __init__(self) -> None:
        self.calls = []

    def subscribe(self, types, local_bulk, metadata_only) -> None:
        self.calls.append((sorted(types), sorted(local_bulk), metadata_only))


def _check(label: str, got, want) -> bool:
    if got != want:
        print(f"FAIL: {label}: got {got!r}, expected {want!r}")
        return False
    return True


def main() -> int:
    bootstrap_hubinterface_paths()
    from image_display_mrson_hub_sink import MrsonHubBridge
    from livesync_subscribers import LiveSyncSub, LiveSyncSubscribers, combine_subscriptions

    ok = True
    fs = frozenset

    combined = combine_subscriptions(
        [
            LiveSyncSub(fs(MIRROR_TYPES), fs({"image", "mesh"}), False),
            LiveSyncSub(fs(IRA_TYPES), fs(), True),
        ]
    )
    ok &= _check("union of types", combined.types, fs(MIRROR_TYPES))
    ok &= _check("full subscriber keeps bulk", combined.metadata_only, False)
    ok &= _check("localBulk from full subscribers only", combined.local_bulk, fs({"image", "mesh"}))

    combined = combine_subscriptions(
        [
            LiveSyncSub(fs(["image"]), fs({"image", "mesh"}), False),
            LiveSyncSub(fs(["mesh"]), fs({"mesh"}), False),
        ]
    )
    ok &= _check("localBulk intersection", combined.local_bulk, fs({"mesh"}))
    ok &= _check(
        "metadata-only when all are",
        combine_subscriptions([LiveSyncSub(fs(IRA_TYPES), fs(), True)]).metadata_only,
        True,
    )
    ok &= _check("no subscribers", combine_subscriptions([]), None)

    reg = LiveSyncSubscribers()
    reg.upsert("Mirror-1", MIRROR_TYPES, [], False, now=0.0)
    reg.upsert("IRA-1", IRA_TYPES, [], True, now=100.0)
    ok &= _check("case-insensitive touch", reg.touch("ira-1", now=150.0), True)
    ok &= _check("has idle", reg.has_idle(180.0, now=200.0), True)
    ok &= _check("prune idle", reg.prune_idle(180.0, now=200.0), ["mirror-1"])
    ok &= _check("IRA kept", reg.names(), ["ira-1"])

    bridge = MrsonHubBridge(connection=None)  # type: ignore[arg-type]
    peer = _FakePeer()

    def attach():
        bridge._peer = peer
        return peer

    bridge.ensure_attached = attach  # type: ignore[method-assign]

    ok &= _check("mirror subscribe", bridge.subscribe_on_main("Mirror-1", MIRROR_TYPES, [], False), True)
    ok &= _check(
        "IRA join covered by mirror: no replay",
        bridge.subscribe_on_main("IRA-1", IRA_TYPES, [], True),
        False,
    )
    ok &= _check("mirror re-subscribe always replays", bridge.subscribe_on_main("Mirror-1", MIRROR_TYPES, [], False), True)
    ok &= _check("mirror leaves, IRA remains", bridge.unsubscribe_on_main("Mirror-1"), False)
    ok &= _check(
        "peer narrowed to IRA metadata-only",
        peer.calls[-1],
        (sorted(IRA_TYPES), [], True),
    )
    ok &= _check("IRA leaves: detach", bridge.unsubscribe_on_main("IRA-1"), True)
    ok &= _check("peer subscribe count", len(peer.calls), 3)

    peer.calls.clear()
    bridge.subscribe_on_main("IRA-1", IRA_TYPES, [], True)
    bridge.subscribe_on_main("Mirror-1", MIRROR_TYPES, [], False)
    ok &= _check(
        "IRA first, then mirror widens to full",
        peer.calls,
        [(sorted(IRA_TYPES), [], True), (sorted(MIRROR_TYPES), [], False)],
    )

    if not ok:
        return 1
    print("OK livesync subscribers (combine, idle prune, shared sink)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
