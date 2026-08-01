# b4m-necromancer Manual Installation

Prefer the automatic path when possible: clone the repo and run `./install.sh` (or `make install-pi`) from the repository root. Use the steps below only if you need a fully manual setup.

1. Install required packages

```bash
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip python3-evdev sane-utils zlib1g-dev libjpeg-dev
```

2. Create log directory

```bash
sudo mkdir -p /var/log/scanner
sudo chown $USER:$USER /var/log/scanner
```

3. Deploy application files

```bash
git clone --branch v0.3.0 https://github.com/b4m-oss/necromancer.git ~/necromancer
# Until the tag exists: --branch dev-v0.3.0 or --branch main
mkdir -p ~/app
cp -r ~/necromancer/app/* ~/app/
mkdir -p ~/app/tmp
```

4. Create a Python virtual environment and install dependencies

```bash
python3 -m venv ~/app/venv
~/app/venv/bin/pip install --upgrade pip
~/app/venv/bin/pip install -r ~/app/requirements.txt
```

5. Set up systemd service

```bash
sudo cp ~/necromancer/app/scanner_service.service /etc/systemd/system/

# Adjust user / group / working directory for your environment
sudo sed -i "s/User=__USER__/User=$USER/g" /etc/systemd/system/scanner_service.service
sudo sed -i "s/Group=__USER__/Group=$USER/g" /etc/systemd/system/scanner_service.service
sudo sed -i "s|__APP_WORKDIR__|${HOME}/app|g" /etc/systemd/system/scanner_service.service
sudo sed -i "s|^ExecStart=/usr/bin/python3 |ExecStart=${HOME}/app/venv/bin/python |g" /etc/systemd/system/scanner_service.service
```

6. Make scripts executable

```bash
chmod +x ~/app/keypad_daemon.py
chmod +x ~/app/lib/scan.py
```

7. Copy upload settings and enable the service

```bash
cp ~/app/config/upload.example.json ~/app/config/upload.json
# Edit upload.json with your credentials (do not commit secrets)

sudo systemctl daemon-reload
sudo systemctl enable scanner_service.service
sudo systemctl start scanner_service.service
```

-------

Done.
