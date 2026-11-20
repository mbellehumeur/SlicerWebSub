"""Short-lived single-use tickets for opening /ws/admin.

Browsers cannot set headers on a WebSocket handshake, so the admin page trades
its admin token (sent as a header) for a ticket that goes in the WS URL. A
ticket that ends up in a log is already used or expired.
"""

from __future__ import annotations

import secrets
import time
from typing import Dict

ADMIN_WS_TICKET_TTL_SECONDS = 30.0

_tickets: Dict[str, float] = {}


def _prune(now: float) -> None:
    for ticket, expires_at in list(_tickets.items()):
        if expires_at <= now:
            _tickets.pop(ticket, None)


def issue_ticket(ttl: float = ADMIN_WS_TICKET_TTL_SECONDS) -> str:
    now = time.monotonic()
    _prune(now)
    ticket = secrets.token_urlsafe(32)
    _tickets[ticket] = now + ttl
    return ticket


def consume_ticket(ticket: str) -> bool:
    """True once for a valid, unexpired ticket; the ticket is removed either way."""
    value = (ticket or "").strip()
    if not value:
        return False
    expires_at = _tickets.pop(value, None)
    if expires_at is None:
        return False
    return expires_at > time.monotonic()
