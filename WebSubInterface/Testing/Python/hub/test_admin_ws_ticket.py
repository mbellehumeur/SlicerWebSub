#!/usr/bin/env python3
"""Offline asserts for single-use /ws/admin tickets (no hub required)."""

from __future__ import annotations

import sys
from pathlib import Path

_PYTHON_ROOT = Path(__file__).resolve().parents[1]
if str(_PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYTHON_ROOT))

from common.local_hub import HUBINTERFACE_ROOT, bootstrap_hubinterface_paths  # noqa: E402


def main() -> int:
    bootstrap_hubinterface_paths()
    sys.path.insert(0, str(HUBINTERFACE_ROOT / "hub" / "Lib"))
    import admin_ws_tickets as tickets

    ticket = tickets.issue_ticket()
    if not ticket or len(ticket) < 32:
        print(f"FAIL: ticket too short: {ticket!r}")
        return 1
    if not tickets.consume_ticket(ticket):
        print("FAIL: fresh ticket rejected")
        return 1
    if tickets.consume_ticket(ticket):
        print("FAIL: ticket accepted twice")
        return 1

    expired = tickets.issue_ticket(ttl=0)
    if tickets.consume_ticket(expired):
        print("FAIL: expired ticket accepted")
        return 1

    for bad in ("", "   ", "not-a-ticket"):
        if tickets.consume_ticket(bad):
            print(f"FAIL: unknown ticket accepted: {bad!r}")
            return 1

    if tickets.issue_ticket() == tickets.issue_ticket():
        print("FAIL: tickets are not unique")
        return 1

    print("OK admin ws tickets are single-use and expire")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
