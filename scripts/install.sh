#!/bin/bash
# Pi install entry (called from repo-root ./install.sh).
# Delegates to app/install.sh (systemd / venv / apt setup).

set -e

resolve_app_install() {
    local here=""
    local root=""
    if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
        here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        # scripts/ → repository root
        root="$(cd "${here}/.." && pwd)"
        if [ -f "${root}/app/install.sh" ]; then
            echo "${root}/app/install.sh"
            return 0
        fi
    fi
    # Fallback: cwd is the repository root
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
    exit 1
}

exec bash "$APP_INSTALL" "$@"
