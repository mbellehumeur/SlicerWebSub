#!/usr/bin/env python3
"""Offline asserts: binary-batch publish rejects oversize bodies before multipart parse."""

from __future__ import annotations

import sys
from pathlib import Path

_PYTHON_ROOT = Path(__file__).resolve().parents[1]
if str(_PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYTHON_ROOT))

from common.local_hub import HUBINTERFACE_ROOT, bootstrap_hubinterface_paths  # noqa: E402


class _OversizeBody(bytes):
    """bytes subclass with a fake ``__len__`` so we need not allocate the cap."""

    def __new__(cls, reported: int):
        obj = super().__new__(cls, b"")
        obj._reported = reported
        return obj

    def __len__(self) -> int:
        return self._reported


def main() -> int:
    bootstrap_hubinterface_paths()
    hub_lib = HUBINTERFACE_ROOT / "hub" / "Lib"
    if str(hub_lib) not in sys.path:
        sys.path.insert(0, str(hub_lib))

    from binary_publish import (
        _assert_body_within_cap,
        _assert_content_length_within_cap,
    )
    from env import HUB_HTTP_PAYLOAD_MAX_TOTAL_BYTES
    from fastapi import HTTPException

    over = HUB_HTTP_PAYLOAD_MAX_TOTAL_BYTES + 1

    try:
        _assert_content_length_within_cap(str(over))
        print("FAIL: oversize Content-Length should raise 413")
        return 1
    except HTTPException as exc:
        if exc.status_code != 413:
            print(f"FAIL: Content-Length expected 413, got {exc.status_code}")
            return 1

    _assert_content_length_within_cap("")
    _assert_content_length_within_cap(None)
    _assert_content_length_within_cap("not-a-number")
    _assert_content_length_within_cap(str(HUB_HTTP_PAYLOAD_MAX_TOTAL_BYTES))
    _assert_content_length_within_cap("0")

    try:
        _assert_body_within_cap(_OversizeBody(over))
        print("FAIL: oversize body should raise 413")
        return 1
    except HTTPException as exc:
        if exc.status_code != 413:
            print(f"FAIL: body expected 413, got {exc.status_code}")
            return 1

    _assert_body_within_cap(b"")
    _assert_body_within_cap(b"ok")
    _assert_body_within_cap(_OversizeBody(HUB_HTTP_PAYLOAD_MAX_TOTAL_BYTES))

    print(
        "OK binary publish body cap "
        f"(max={HUB_HTTP_PAYLOAD_MAX_TOTAL_BYTES})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
