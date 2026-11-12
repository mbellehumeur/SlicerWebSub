"""Browser + loopback helper for hub-mediated OIDC (native / desktop clients)."""

from __future__ import annotations

import asyncio
import logging
import webbrowser
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from aiohttp import web

LOGGER = logging.getLogger("hub_client.oidc_browser")

_SUCCESS_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Hub login</title></head>
<body style="font-family:system-ui,sans-serif;padding:2rem">
<h1>Login complete</h1>
<p>You can close this tab and return to the application.</p>
</body></html>
"""


async def capture_loopback_query_params(
    *,
    timeout_s: float = 300.0,
    hub_auth: str = "oidc",
    waiting_text: str = "Waiting for hub login…",
    on_listening: Optional[Any] = None,
) -> Dict[str, str]:
    """Bind ``127.0.0.1:0``, call ``on_listening(return_to)``, wait for query callback.

    Completes when the callback includes ``access_token`` and matching ``hub_auth``.
    """
    expected_auth = str(hub_auth or "").strip().lower() or "oidc"
    loop = asyncio.get_running_loop()
    result_future: asyncio.Future[Dict[str, str]] = loop.create_future()

    async def handle_callback(request: web.Request) -> web.Response:
        params = {k: str(v) for k, v in request.rel_url.query.items()}
        auth = str(params.get("hub_auth") or "").strip().lower()
        access = str(params.get("access_token") or "").strip()
        auth_ok = auth == expected_auth or (
            expected_auth == "worklist" and bool(access) and not auth
        )
        if not auth_ok or not access:
            return web.Response(text=waiting_text, content_type="text/plain")
        if not result_future.done():
            result_future.set_result(params)
        return web.Response(text=_SUCCESS_HTML, content_type="text/html")

    app = web.Application()
    app.router.add_get("/", handle_callback)
    app.router.add_get("/{path:.*}", handle_callback)

    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    try:
        sockets = site._server.sockets if site._server else None  # type: ignore[attr-defined]
        if not sockets:
            raise RuntimeError("Loopback server failed to bind")
        port = int(sockets[0].getsockname()[1])
        return_to = f"http://127.0.0.1:{port}/"
        if callable(on_listening):
            on_listening(return_to)
        try:
            return await asyncio.wait_for(result_future, timeout=timeout_s)
        except asyncio.TimeoutError as exc:
            raise TimeoutError(
                f"Loopback callback timed out after {timeout_s:.0f}s"
            ) from exc
    finally:
        await runner.cleanup()


def capture_loopback_query_params_sync(
    *,
    timeout_s: float = 300.0,
    hub_auth: str = "worklist",
    waiting_text: str = "Waiting for worklist credentials…",
    on_listening: Optional[Any] = None,
) -> Dict[str, str]:
    """Sync wrapper for :func:`capture_loopback_query_params` (Qt / desktop)."""
    return asyncio.run(
        capture_loopback_query_params(
            timeout_s=timeout_s,
            hub_auth=hub_auth,
            waiting_text=waiting_text,
            on_listening=on_listening,
        )
    )


async def capture_hub_oidc_tokens(
    *,
    login_url: str,
    timeout_s: float = 300.0,
    open_browser: bool = True,
) -> Dict[str, str]:
    """Open hub ``/oauth/login`` with ``response_mode=query`` and capture tokens.

    ``login_url`` should already be the hub login endpoint (no query), e.g.
    ``https://host/oauth/login``. This function appends ``return_to`` and
    ``response_mode=query``.
    """

    def _open_login(return_to: str) -> None:
        query = urlencode(
            {
                "return_to": return_to,
                "response_mode": "query",
            }
        )
        full_login = f"{login_url.rstrip('/')}?{query}"
        LOGGER.info("OIDC browser login: opening %s", full_login.split("?", 1)[0])
        if open_browser:
            opened = webbrowser.open(full_login)
            if not opened:
                LOGGER.warning(
                    "webbrowser.open returned False; open this URL manually: %s",
                    full_login,
                )
        else:
            LOGGER.info("OIDC open_browser=False; visit: %s", full_login)

    return await capture_loopback_query_params(
        timeout_s=timeout_s,
        hub_auth="oidc",
        waiting_text="Waiting for hub OIDC login…",
        on_listening=_open_login,
    )


def apply_oidc_session_tokens(
    tokens: Dict[str, Any],
) -> Dict[str, str]:
    """Normalize loopback/query token dict for the hub client."""
    access = str(tokens.get("access_token") or "").strip()
    if not access:
        raise RuntimeError("OIDC callback missing access_token")
    return {
        "access_token": access,
        "id_token": str(tokens.get("id_token") or "").strip(),
        "topic": str(tokens.get("topic") or "").strip(),
        "user_name": str(tokens.get("user_name") or "").strip(),
        "expires_in": str(tokens.get("expires_in") or "").strip(),
    }
