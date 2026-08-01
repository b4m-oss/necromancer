#!/bin/bash
# Installation script for the document scanner system.
#
# This script deploys files from the repository's app directory
# into the runtime directory ($HOME/app) and sets up a systemd service.
#
# Python dependencies are installed only inside $HOME/app/venv so that
# Raspberry Pi OS (PEP 668 / externally-managed-environment) is satisfied.

set -e

APP_SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DST_DIR="$HOME/app"
VENV_PY="${APP_DST_DIR}/venv/bin/python"

echo "Installing required packages..."
sudo apt-get update
sudo apt-get install -y \
    python3-venv \
    python3-pip \
    python3-evdev \
    sane-utils \
    zlib1g-dev \
    libjpeg-dev

echo "Deploying application files to ${APP_DST_DIR}..."
mkdir -p "$APP_DST_DIR"
cp -r "${APP_SRC_DIR}/"* "$APP_DST_DIR/"

# Pi deploy copies only app/ → $HOME/app. Runtime pins live in requirements.txt
# (kept in sync with repo-root pyproject.toml). Full-repo editable install is for
# host/Docker development only (see Makefile / Dockerfile).
REQ_FILE="${APP_DST_DIR}/requirements.txt"
if [ ! -f "$REQ_FILE" ]; then
    echo "ERROR: requirements.txt not found at ${REQ_FILE}"
    echo "The install script directory is: ${APP_SRC_DIR}"
    echo "Add app/requirements.txt to your repository (e.g. evdev and Pillow), then re-run this script."
    exit 1
fi

echo "Creating Python virtual environment..."
if [ ! -x "$VENV_PY" ]; then
    python3 -m venv "${APP_DST_DIR}/venv"
else
    echo "Reusing existing virtual environment at ${APP_DST_DIR}/venv"
fi

echo "Installing Python packages into virtual environment..."
"$VENV_PY" -m pip install --upgrade pip
"$VENV_PY" -m pip install -r "$REQ_FILE"

echo "Verifying Pillow (PIL) in virtual environment..."
"$VENV_PY" -c "from PIL import Image; print('Pillow OK:', Image.__version__)"

echo "Creating log directory..."
sudo mkdir -p /var/log/scanner
sudo chown "$USER:$USER" /var/log/scanner

echo "Creating temporary directory for scans..."
mkdir -p "$APP_DST_DIR/tmp"

echo "Installing systemd service..."
# Copy service file (treated as a template)
sudo cp "$APP_DST_DIR/scanner_service.service" /etc/systemd/system/

# Replace template placeholders with current user and app path.
# Expand __APP_WORKDIR__ everywhere first, then swap system Python for venv (keypad_daemon
# launches scan.py with sys.executable, so both must use the venv interpreter).
sudo sed -i "s/User=__USER__/User=$USER/g" /etc/systemd/system/scanner_service.service
sudo sed -i "s/Group=__USER__/Group=$USER/g" /etc/systemd/system/scanner_service.service
sudo sed -i "s|__APP_WORKDIR__|${APP_DST_DIR}|g" /etc/systemd/system/scanner_service.service
sudo sed -i "s|^ExecStart=/usr/bin/python3 |ExecStart=${APP_DST_DIR}/venv/bin/python |g" /etc/systemd/system/scanner_service.service

echo "Adding convenient CLI alias (necro) to shell config..."
for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
    if [ -f "$rc" ]; then
        if ! grep -q "b4m-necromancer: necro CLI (lib.scan)" "$rc"; then
            cat >> "$rc" <<'EOF'
# b4m-necromancer: necro CLI (lib.scan)
alias necro='PYTHONPATH="$HOME/app" "$HOME/app/venv/bin/python" -m lib.scan'
EOF
            echo "Alias added to $rc"
        else
            echo "necro alias marker already present in $rc"
        fi
    fi
done

echo "Making scripts executable..."
chmod +x "${APP_DST_DIR}/keypad_daemon.py"
chmod +x "${APP_DST_DIR}/lib/scan.py"

echo "Enabling systemd service..."
sudo systemctl daemon-reload
sudo systemctl enable scanner_service.service

echo "Installation finished!"
echo "To start the service: sudo systemctl start scanner_service.service"
echo "To check status:      sudo systemctl status scanner_service.service"
echo ""
echo "Start the service now? [y/N]"
read -r start_service

if [[ "$start_service" == "y" || "$start_service" == "Y" ]]; then
    echo "Starting service..."
    sudo systemctl start scanner_service.service
    echo "Service status:"
    sudo systemctl status scanner_service.service
else
    echo "Service was not started. You can start it manually later."
fi

echo "Setup complete!"
