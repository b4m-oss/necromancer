# b4m-necromancer Manual Installation

1. 必要なパッケージをインストールします

```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-evdev sane-utils
```

2. ログディレクトリを作成します

```bash
sudo mkdir -p /var/log/scanner
sudo chown $USER:$USER /var/log/scanner
```

3. アプリケーションファイルを配置します

```bash
git clone https://github.com/b4m-oss/b4m-necromancer.git ~/b4m-necromancer
mkdir -p ~/app
cp -r ~/b4m-necromancer/app/* ~/app/
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
sudo cp ~/b4m-necromancer/app/scanner_service.service /etc/systemd/system/

# ユーザー名・パスを現在の環境に合わせて修正
sudo sed -i "s/User=kohki/User=$USER/g" /etc/systemd/system/scanner_service.service
sudo sed -i "s/Group=kohki/Group=$USER/g" /etc/systemd/system/scanner_service.service
sudo sed -i "s|WorkingDirectory=/home/kohki/app|WorkingDirectory=/home/$USER/app|g" /etc/systemd/system/scanner_service.service
sudo sed -i "s|ExecStart=/home/kohki/myscan/bin/python3 /home/kohki/app/keypad_daemon.py|ExecStart=/home/$USER/app/venv/bin/python /home/$USER/app/keypad_daemon.py|g" /etc/systemd/system/scanner_service.service
sudo sed -i '/^Environment="PYTHONPATH=/d' /etc/systemd/system/scanner_service.service
```

6. 実行権限を設定します

```bash
chmod +x ~/b4m-necromancer/app/keypad_daemon.py
chmod +x ~/b4m-necromancer/app/lib/scan.py
```

7. サービスを有効化して開始します

```bash
sudo systemctl daemon-reload
sudo systemctl enable scanner_service.service
sudo systemctl start scanner_service.service
```

-------

以上