# b4m-necromancer - revive your old scanner with Raspberry Pi ZERO 2

[![CI](https://github.com/b4m-oss/necromancer/actions/workflows/ci.yml/badge.svg)](https://github.com/b4m-oss/necromancer/actions/workflows/ci.yml)

[日本語版](./README_ja.md)

This system is a small solution to automate document scanning from a numeric keypad.  
By pressing a number key on the keypad and then Enter, you can trigger different scan modes.

## Motivation

Bring EOL (end-of-life) scanners back to life with OSS.

The author used a Fujitsu ScanSnap iX500. At some point, the official iOS app support was dropped.  
Because uploading scanned documents over Wi-Fi was still an essential workflow, various alternatives were explored.  
As a result, SANE was discovered, and the idea came up to drive the scanner from a Raspberry Pi Zero 2 over the network.

## What does it do?

- Keep using a scanner that has lost official software support.
- Automatically upload scanned documents to a cloud service.
- Prepare fine-grained presets for different scan modes.
- Operate everything from a numeric keypad.

## Required hardware

- Raspberry Pi Zero 2W (or another Raspberry Pi)
- ScanSnap iX500 (or another SANE-compatible scanner)
- Numeric keypad (USB or Bluetooth)

## Features

- Monitor input from a numeric keypad.
- Execute different scan modes per number key (diary, receipt, flyer).
- Automatically upload scanned documents to Nextcloud (via WebDAV).
- Start the keypad daemon automatically at system boot (systemd service).
- Log scan activity to a log file.


## Installation

### Automatic installation

On a Raspberry Pi, clone the repo and run the root installer (delegates to `app/install.sh`).

**Recommended** (after the `v0.3.0` release tag exists):

```bash
git clone --branch v0.3.0 https://github.com/b4m-oss/necromancer.git ~/necromancer
cd ~/necromancer && ./install.sh
```

Until the tag is published, use a development branch instead:

```bash
git clone --branch dev-v0.3.0 https://github.com/b4m-oss/necromancer.git ~/necromancer
# or: --branch main
cd ~/necromancer && ./install.sh
```

You can also run `make install-pi` from the repository root (same as `./install.sh`).

**Optional** (from a cloned repository root; prefers the tagged script):

```bash
curl -fsSL https://raw.githubusercontent.com/b4m-oss/necromancer/v0.3.0/install.sh | bash
```

After install, copy `~/app/config/upload.example.json` → `~/app/config/upload.json` and edit credentials (do not commit secrets). See [Setup and configuration](./docs/en/setup_config.md).

### Manual installation

See [Manual installation](./docs/en/manual_installation.md)  
日本語版: [手動インストール](./docs/ja/manual_installation.md)

## Setup and configuration

See [Setup and configuration](./docs/en/setup_config.md)  
日本語版: [セットアップと設定](./docs/ja/setup_config.md)

## How to use

Once the system is running, the keypad daemon starts automatically and waits for input.  
Use the keypad as follows:

1. Press `1` on the keypad → Enter: scan with the mode mapped from `mode.json` `keybindings["1"]` (default: `diary`).
2. Press `2` on the keypad → Enter: scan with `keybindings["2"]` (default: `receipt`).
3. Press `3` on the keypad → Enter: scan with `keybindings["3"]` (default: `flyer`).

If you do not press Enter within 5 seconds after pressing a digit, the input buffer is cleared.  
Pressing another digit overwrites the previous one.

### Configuration dump (`--dump-config`)

When you want to verify **“which exact command and upload path will be used for a given mode”** before running a real scan, use the `--dump-config` option.

- Config files read:
  - `app/config/scanner.json`
  - `app/config/mode.json`
  - `app/config/upload.json`
- It prints:
  - The effective `scanimage` batch command line for the selected mode
  - Upload target information (provider, endpoint, upload folder, remote path pattern, delete-after-upload flag, etc.)

#### Usage

From a development checkout:

```bash
python3 -m app.lib.scan --dump-config diary
```

On an installed system, the `install.sh` script adds a `necro` alias to your shell (for bash/zsh). After opening a new shell (or `source ~/.bashrc` / `source ~/.zshrc`), you can simply run:

```bash
necro --dump-config diary
```

#### Sample output (excerpt)

```text
Mode: diary

=== scanimage command (batch) ===
scanimage --device="fujitsu:ScanSnap iX500:17872" --resolution=200 ...

Parameters:
- device_name: fujitsu:ScanSnap iX500:17872
- resolution: 200
- mode: Color
- source: ADF Duplex
- format: jpeg
- output_pattern: /.../tmp/{timestamp}/diary-%d.jpg
- extra_options: ['--swdeskew=yes', '--page-width=210', '--page-height=305']

=== upload target ===
provider          : nextcloud
endpoint          : https://example.com/remote.php/dav/files/user/
upload_folder     : Scans/
strategy          : pdf
remote_path       : Scans/diary-{timestamp}.pdf
delete_after_upload: False
```

- At runtime, `{timestamp}` is replaced with the actual timestamp used for the scan.
- **Note:** `--dump-config` is read-only: it does not perform any scan or upload; it just shows what would happen.

## Local development (host / Docker)

Dependencies are declared in root `pyproject.toml` (`requires-python >=3.11`, including the `dev` extra for pytest).  
Raspberry Pi install still uses `app/requirements.txt` via `app/install.sh` (kept in sync with the runtime pins in `pyproject.toml`).

### Host (Python 3.11)

```bash
make install-dev   # creates .venv and runs: pip install -e ".[dev]"
make test
make test-cov
```

On macOS, `evdev` is skipped (Linux marker); tests use the existing fake/mock pattern.

### Docker (Python 3.11 fixed)

Dev image and Compose files live under `docker/`.

```bash
make docker-build
make docker-test
```

Or with Compose / `docker run`:

```bash
docker compose -f docker/docker-compose.yml build
docker compose -f docker/docker-compose.yml run --rm dev
# equivalent image run after build:
docker run --rm -v "$PWD":/workspace -w /workspace b4m-necromancer-dev:3.11 \
  sh -c "pip install -q -e '.[dev]' && pytest -q"
```

See also [Developers' guide](./docs/dev/_developers_guide.md).

## Troubleshooting

See [Troubleshooting](./docs/en/troubleshoot.md)  
日本語版: [トラブルシューティング](./docs/ja/troubleshoot.md)

## Support

**Disclaimer**  
This software is provided as-is, without any official support.  
The author assumes no responsibility for any damage or loss caused by the use of this software.  
By using this software, you agree to these terms.

### Paid support

If you need custom work such as support for other scanners or other cloud storage services,  
paid support and customization are available.  
Please contact [B4M LLC](https://b4m.co.jp/).

## License

This project is released under the MIT License. See the `LICENSE` file for details.


-------------

Developed by Kohki SHIKATA / B4M LLC. from Osaka with ❤️

