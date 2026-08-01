#!/bin/bash
# Thin wrapper kept at repo root for docs and one-liner compatibility.
# Delegates to scripts/install.sh → app/install.sh.
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
exec bash "${ROOT}/scripts/install.sh" "$@"
