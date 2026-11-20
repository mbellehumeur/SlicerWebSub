"""LiveSync subscribers sharing Image Display's single ModuleServer Hub sink peer.

The sink peer holds one subscription (types / localBulk / metadataOnly). Each Hub client
(slicer-mirror, IRA, ...) subscribes separately; the peer runs the combination so a
metadata-only follower never narrows what a full mirror receives.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Iterable, List, NamedTuple, Optional


@dataclass
class LiveSyncSub:
    types: FrozenSet[str]
    local_bulk: FrozenSet[str]
    metadata_only: bool
    last_seen: float = field(default_factory=time.monotonic)


class CombinedSubscription(NamedTuple):
    types: FrozenSet[str]
    local_bulk: FrozenSet[str]
    metadata_only: bool


def _clean(values: Optional[Iterable[str]]) -> FrozenSet[str]:
    return frozenset(str(v).strip() for v in (values or ()) if str(v).strip())


def combine_subscriptions(subs: Iterable[LiveSyncSub]) -> Optional[CombinedSubscription]:
    """Union of types; metadata-only only when every subscriber is; localBulk only when every
    bulk-receiving subscriber reproduces that type locally."""
    subs = list(subs)
    if not subs:
        return None
    types = frozenset().union(*(s.types for s in subs))
    metadata_only = all(s.metadata_only for s in subs)
    full = [s for s in subs if not s.metadata_only]
    if full:
        local_bulk = frozenset.intersection(*(s.local_bulk for s in full))
    else:
        local_bulk = frozenset().union(*(s.local_bulk for s in subs))
    return CombinedSubscription(types, local_bulk, metadata_only)


class LiveSyncSubscribers:
    """Per-subscriber registry keyed by Hub ``subscriber.name`` (case-insensitive)."""

    def __init__(self) -> None:
        self._subs: Dict[str, LiveSyncSub] = {}

    @staticmethod
    def _key(name: str) -> str:
        return str(name or "").strip().lower()

    def __len__(self) -> int:
        return len(self._subs)

    def names(self) -> List[str]:
        return sorted(self._subs)

    def upsert(
        self,
        name: str,
        types: Iterable[str],
        local_bulk: Iterable[str],
        metadata_only: bool,
        now: Optional[float] = None,
    ) -> None:
        self._subs[self._key(name)] = LiveSyncSub(
            types=_clean(types),
            local_bulk=_clean(local_bulk),
            metadata_only=bool(metadata_only),
            last_seen=time.monotonic() if now is None else now,
        )

    def remove(self, name: str) -> bool:
        return self._subs.pop(self._key(name), None) is not None

    def touch(self, name: str, now: Optional[float] = None) -> bool:
        sub = self._subs.get(self._key(name))
        if sub is None:
            return False
        sub.last_seen = time.monotonic() if now is None else now
        return True

    def has_idle(self, max_age: float, now: Optional[float] = None) -> bool:
        now = time.monotonic() if now is None else now
        return any(now - s.last_seen >= max_age for s in list(self._subs.values()))

    def prune_idle(self, max_age: float, now: Optional[float] = None) -> List[str]:
        now = time.monotonic() if now is None else now
        stale = [k for k, s in self._subs.items() if now - s.last_seen >= max_age]
        for k in stale:
            del self._subs[k]
        return stale

    def combined(self) -> Optional[CombinedSubscription]:
        return combine_subscriptions(self._subs.values())
