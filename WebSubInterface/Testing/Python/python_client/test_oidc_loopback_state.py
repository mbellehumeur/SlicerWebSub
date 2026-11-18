#!/usr/bin/env python3
"""Offline asserts for OIDC loopback client_state CSRF bind."""

from __future__ import annotations

import asyncio
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

_PYTHON_ROOT = Path(__file__).resolve().parents[1]
if str(_PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYTHON_ROOT))

from common.local_hub import bootstrap_hubinterface_paths  # noqa: E402


async def _run() -> None:
    root = bootstrap_hubinterface_paths()
    # Prefer this checkout over any separately installed hub_client.
    src = str(root / "python_client" / "src")
    if src in sys.path:
        sys.path.remove(src)
    sys.path.insert(0, src)
    from hub_client.oidc_browser import capture_loopback_query_params

    client_state = "test-client-state-abc123"
    return_to_holder: dict[str, str] = {}

    def on_listening(return_to: str) -> None:
        return_to_holder["url"] = return_to

    task = asyncio.create_task(
        capture_loopback_query_params(
            timeout_s=10.0,
            hub_auth="oidc",
            waiting_text="waiting",
            on_listening=on_listening,
            client_state=client_state,
        )
    )
    for _ in range(50):
        if return_to_holder.get("url"):
            break
        await asyncio.sleep(0.05)
    base = return_to_holder.get("url")
    if not base:
        raise RuntimeError("loopback did not publish return_to")

    def _get(query: dict[str, str]) -> int:
        url = base + ("&" if "?" in base else "?") + urllib.parse.urlencode(query)
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                return int(resp.status)
        except urllib.error.HTTPError as exc:
            return int(exc.code)

    # Missing client_state must not complete the future.
    status = await asyncio.to_thread(
        _get,
        {"hub_auth": "oidc", "access_token": "attacker-token"},
    )
    if status != 200:
        raise RuntimeError(f"expected 200 waiting page, got {status}")
    await asyncio.sleep(0.2)
    if task.done():
        raise RuntimeError("loopback accepted callback without client_state")

    # Wrong client_state must not complete.
    status = await asyncio.to_thread(
        _get,
        {
            "hub_auth": "oidc",
            "access_token": "attacker-token",
            "client_state": "wrong-state",
        },
    )
    if status != 200:
        raise RuntimeError(f"expected 200 waiting page, got {status}")
    await asyncio.sleep(0.2)
    if task.done():
        raise RuntimeError("loopback accepted callback with wrong client_state")

    # Matching client_state completes.
    status = await asyncio.to_thread(
        _get,
        {
            "hub_auth": "oidc",
            "access_token": "good-token",
            "client_state": client_state,
            "topic": "user@example.com",
        },
    )
    if status != 200:
        raise RuntimeError(f"expected 200 success page, got {status}")
    params = await asyncio.wait_for(task, timeout=5.0)
    if params.get("access_token") != "good-token":
        raise RuntimeError(f"unexpected tokens: {params}")
    if params.get("client_state") != client_state:
        raise RuntimeError(f"client_state not echoed in result: {params}")


def main() -> int:
    try:
        asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001 - script exit
        print(f"FAIL: {exc}")
        return 1
    print("OK oidc loopback client_state bind")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
