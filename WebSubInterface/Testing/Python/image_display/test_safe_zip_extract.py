#!/usr/bin/env python3
"""Offline asserts for Zip Slip rejection in image_display_client_load."""

from __future__ import annotations

import io
import sys
import tempfile
import zipfile
from pathlib import Path

_PYTHON_ROOT = Path(__file__).resolve().parents[1]
if str(_PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYTHON_ROOT))

from common.local_hub import bootstrap_hubinterface_paths  # noqa: E402


def main() -> int:
    bootstrap_hubinterface_paths()
    from safe_zip import safe_extract_zip

    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "out"
        dest.mkdir()

        safe_buf = io.BytesIO()
        with zipfile.ZipFile(safe_buf, "w") as zf:
            zf.writestr("study/a.dcm", b"ok")
        safe_buf.seek(0)
        with zipfile.ZipFile(safe_buf, "r") as zf:
            safe_extract_zip(zf, dest)
        assert (dest / "study" / "a.dcm").is_file()

        bad_buf = io.BytesIO()
        with zipfile.ZipFile(bad_buf, "w") as zf:
            zf.writestr("../escape.txt", b"nope")
        bad_buf.seek(0)
        try:
            with zipfile.ZipFile(bad_buf, "r") as zf:
                safe_extract_zip(zf, dest)
            print("FAIL: expected unsafe zip path rejection")
            return 1
        except RuntimeError as exc:
            if "Unsafe zip path" not in str(exc):
                print(f"FAIL: unexpected error: {exc}")
                return 1

    print("OK safe zip extract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
