#!/bin/bash
# Thin wrapper: run from the necromancer repository root to install on a Pi.
# Delegates to app/install.sh (systemd / venv / apt setup).

set -e

resolve_app_install() {
    local script_dir=""
    # Prefer the directory of this script when it is a real file (./install.sh).
    if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
        script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        if [ -f "${script_dir}/app/install.sh" ]; then
            echo "${script_dir}/app/install.sh"
            return 0
        fi
    fi
    # Fallback for curl|bash from a cloned repo root (cwd must be the repo).
    if [ -f "$(pwd)/app/install.sh" ]; then
        echo "$(pwd)/app/install.sh"
        return 0
    fi
    return 1
}

APP_INSTALL="$(resolve_app_install)" || {
    echo "ERROR: app/install.sh not found." >&2
    echo "Clone the repository and run this script from the repository root:" >&2
    echo "  git clone --branch v0.3.0 https://github.com/b4m-oss/necromancer.git ~/necromancer" >&2
    echo "  cd ~/necromancer && ./install.sh" >&2
    echo "(Until the v0.3.0 tag exists, use --branch dev-v0.3.0 or --branch main.)" >&2
    exit 1
}

exec bash "$APP_INSTALL" "$@"
