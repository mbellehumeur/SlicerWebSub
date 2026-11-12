#!/usr/bin/env bash
# Build + sync all hub SPA clients into hub/ (Fly / Docker / make_zip prep).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
exec python "$ROOT/scripts/build_all_clients.py" "$@"
