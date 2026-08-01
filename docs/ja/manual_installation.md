# b4m-necromancer Manual Installation

可能なら自動インストールを推奨します。リポジトリをクローンし、ルートで `./install.sh`（または `make install-pi`）を実行してください。以下は手動セットアップが必要な場合のみ使います。

1. 必要なパッケージをインストールします

```bash
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip python3-evdev sane-utils zlib1g-dev libjpeg-dev
```

2. ログディレクトリを作成します

```bash
sudo mkdir -p /var/log/scanner
sudo chown $USER:$USER /var/log/scanner
```

3. アプリケーションファイルを配置します

```bash
git clone --branch v0.3.0 https://github.com/b4m-oss/necromancer.git ~/necromancer
# タグ未公開時: --branch dev-v0.3.0 または --branch main
mkdir -p ~/app
cp -r ~/necromancer/app/* ~/app/
mkdir -p ~/app/tmp
```

4. Python 仮想環境を作成し、依存パッケージをインストールします

```bash
python3 -m venv ~/app/venv
~/app/venv/bin/pip install --upgrade pip
~/app/venv/bin/pip install -r ~/app/requirements.txt
```

5. systemdサービスをセットアップします

```bash
sudo cp ~/necromancer/app/scanner_service.service /etc/systemd/system/

# ユーザー名・パスを現在の環境に合わせて修正
sudo sed -i "s/User=__USER__/User=$USER/g" /etc/systemd/system/scanner_service.service
sudo sed -i "s/Group=__USER__/Group=$USER/g" /etc/systemd/system/scanner_service.service
sudo sed -i "s|__APP_WORKDIR__|${HOME}/app|g" /etc/systemd/system/scanner_service.service
sudo sed -i "s|^ExecStart=/usr/bin/python3 |ExecStart=${HOME}/app/venv/bin/python |g" /etc/systemd/system/scanner_service.service
```

6. 実行権限を設定します

```bash
chmod +x ~/app/keypad_daemon.py
chmod +x ~/app/lib/scan.py
```

7. アップロード設定をコピーし、サービスを有効化して開始します

```bash
cp ~/app/config/upload.example.json ~/app/config/upload.json
# upload.json を編集して認証情報を設定（秘密情報はコミットしない）

sudo systemctl daemon-reload
sudo systemctl enable scanner_service.service
sudo systemctl start scanner_service.service
```

-------

以上
