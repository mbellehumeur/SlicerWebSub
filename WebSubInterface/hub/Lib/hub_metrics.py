"""Process and hub connection metrics for the admin portal."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

_process: Optional[Any] = None
# Hub worker process lifetime (set when this module is first imported).
_HUB_STARTED_AT = datetime.now(timezone.utc)
_HUB_STARTED_MONO = time.monotonic()
# Host net_io baseline at first metrics sample (GB in/out since hub start).
_NET_IO_BASE: Optional[Tuple[int, int]] = None


def _hub_process() -> Any:
    global _process
    if _process is None:
        import psutil

        _process = psutil.Process(os.getpid())
        _process.cpu_percent(interval=None)
    return _process


def _network_bytes_since_start() -> Tuple[Optional[int], Optional[int]]:
    """Host bytes received/sent since hub metrics baseline (first sample)."""
    global _NET_IO_BASE
    try:
        import psutil

        counters = psutil.net_io_counters()
        if counters is None:
            return None, None
        recv = int(counters.bytes_recv)
        sent = int(counters.bytes_sent)
        if _NET_IO_BASE is None:
            _NET_IO_BASE = (recv, sent)
        base_recv, base_sent = _NET_IO_BASE
        return max(0, recv - base_recv), max(0, sent - base_sent)
    except (AttributeError, OSError, PermissionError, TypeError, ValueError):
        return None, None


def collect_hub_metrics(hub: Any, payload_store: Any) -> Dict[str, Any]:
    """Sample RSS, CPU, WebSocket counts, and optional TCP connections."""
    proc = _hub_process()
    mem = proc.memory_info()
    memory_rss_mb = round(mem.rss / (1024 * 1024), 2)
    cpu_percent = round(proc.cpu_percent(interval=None), 2)

    payload_bytes = 0
    if payload_store is not None and hasattr(payload_store, "total_bytes"):
        try:
            payload_bytes = int(payload_store.total_bytes())
        except (TypeError, ValueError):
            payload_bytes = 0
    memory_payload_mb = round(payload_bytes / (1024 * 1024), 2)

    ws_subscribers = len(getattr(hub, "websocket_connections", {}) or {})
    ws_admin = len(getattr(hub, "admin_websockets", []) or [])
    websocket_total = ws_subscribers + ws_admin

    tcp_connections: Optional[int] = None
    try:
        conns = proc.net_connections(kind="inet")
        tcp_connections = len(conns)
    except (AttributeError, OSError, PermissionError):
        tcp_connections = None

    sockets: Dict[str, Any] = {
        "websocket_total": websocket_total,
        "websocket_subscribers": ws_subscribers,
        "websocket_admin": ws_admin,
    }
    if tcp_connections is not None:
        sockets["tcp_connections"] = tcp_connections

    network_chart_value = (
        tcp_connections if tcp_connections is not None else websocket_total
    )
    bytes_recv, bytes_sent = _network_bytes_since_start()
    network: Dict[str, Any] = {
        "chart_value": network_chart_value,
        "websocket_total": websocket_total,
        "websocket_subscribers": ws_subscribers,
        "websocket_admin": ws_admin,
    }
    if tcp_connections is not None:
        network["tcp_connections"] = tcp_connections
    if bytes_recv is not None and bytes_sent is not None:
        network["bytes_recv"] = bytes_recv
        network["bytes_sent"] = bytes_sent
        network["gb_in"] = round(bytes_recv / (1024**3), 3)
        network["gb_out"] = round(bytes_sent / (1024**3), 3)

    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "started_at": _HUB_STARTED_AT.isoformat(),
        "uptime_seconds": round(time.monotonic() - _HUB_STARTED_MONO, 1),
        "memory_rss_mb": memory_rss_mb,
        "memory_payload_mb": memory_payload_mb,
        "cpu_percent": cpu_percent,
        "sockets": sockets,
        "network": network,
    }
