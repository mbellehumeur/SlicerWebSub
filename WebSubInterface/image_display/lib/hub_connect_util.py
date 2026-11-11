"""Small hub connect helpers for Image Display (no workers dependency)."""

from __future__ import annotations

def format_connect_failure(exc: BaseException) -> str:
    """Short, user-facing reason for a failed hub connect."""
    if isinstance(exc, RuntimeError):
        return str(exc).strip() or exc.__class__.__name__

    text = str(exc).strip()
    lowered = text.lower()
    root: BaseException = exc
    cause = exc.__cause__ or exc.__context__
    while cause is not None and cause is not root:
        root = cause
        cause = getattr(cause, "__cause__", None) or getattr(cause, "__context__", None)

    root_name = root.__class__.__name__
    root_text = str(root).strip()
    root_lower = root_text.lower()

    if "refused" in lowered or "refused" in root_lower:
        return "connection refused (hub not reachable)"
    if (
        "timed out" in lowered
        or "timeout" in lowered
        or "timed out" in root_lower
        or root_name.endswith("TimeoutError")
    ):
        return "connection timed out"
    if (
        "name or service not known" in lowered
        or "getaddrinfo failed" in lowered
        or "nodename nor servname" in lowered
    ):
        return "DNS lookup failed"
    if "ssl" in lowered and ("certificate" in lowered or "handshake" in lowered):
        return f"TLS/SSL error: {root_text or text}"
    if "Cannot connect to host" in text:
        return text
    if root_text and root_text != text:
        return f"{root_name}: {root_text}"
    if text:
        return f"{exc.__class__.__name__}: {text}"
    return exc.__class__.__name__
