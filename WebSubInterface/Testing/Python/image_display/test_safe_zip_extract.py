#!/usr/bin/env python3
"""Offline asserts for Zip Slip rejection and size/count caps."""

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

        many_buf = io.BytesIO()
        with zipfile.ZipFile(many_buf, "w") as zf:
            for i in range(5):
                zf.writestr(f"f{i}.dcm", b"x")
        many_buf.seek(0)
        try:
            with zipfile.ZipFile(many_buf, "r") as zf:
                safe_extract_zip(zf, dest / "many", max_members=3)
            print("FAIL: expected too-many-members rejection")
            return 1
        except RuntimeError as exc:
            if "too many members" not in str(exc):
                print(f"FAIL: unexpected error: {exc}")
                return 1

        big_buf = io.BytesIO()
        with zipfile.ZipFile(big_buf, "w") as zf:
            zf.writestr("big.dcm", b"abcdefghij")
        big_buf.seek(0)
        try:
            with zipfile.ZipFile(big_buf, "r") as zf:
                safe_extract_zip(zf, dest / "big", max_total_bytes=5)
            print("FAIL: expected size-limit rejection")
            return 1
        except RuntimeError as exc:
            msg = str(exc)
            if "too large" not in msg and "exceeded size limit" not in msg:
                print(f"FAIL: unexpected error: {exc}")
                return 1

    print("OK safe zip extract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
