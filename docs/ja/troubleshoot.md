# b4m-necromancer トラブルシューティング

## サービスの状態確認

```bash
sudo systemctl status scanner_service.service
```

## ログの確認

```bash
tail -f /var/log/scanner/scanner.log
```

## 手動実行

```bash
# 対話モード（インストール済みの ~/app を直接実行）
python3 ~/app/keypad_scanner.py

# デーモンモード
python3 ~/app/keypad_daemon.py
```

## デバイスパスの指定

特定のテンキーパッドを使用する場合：

```bash
python3 ~/app/keypad_daemon.py --device /dev/input/event0
```

## SSH / ネットワークが遅い・一時的に入れないとき

Raspberry Pi Zero 2 W では、本体は生きているが Wi‑Fi だけ落ちて、数分後に SSH できるように見えることがあります（深いスリープというより無線の再接続寄り）。USB Hub 給電だと電源不足も疑います。

SSH で入れた直後に、次を確認する。

### 1. 電源・スロットル

```bash
vcgencmd get_throttled
vcgencmd measure_volts
```

- `throttled=0x0` … いま電源／サーマル制限のフラグなし
- 非ゼロ … under-voltage 等の可能性（Hub 給電より壁コンセント直結の 5V アダプタを推奨）
- `measure_volts` は SoC コア電圧で、USB 5V そのものではない

### 2. Wi‑Fi / DHCP まわりのログ

```bash
journalctl --since "1 hour ago" --no-pager | grep -iE 'wlan|brcmfmac|wifi|dhcp|disconnect|associate|NetworkManager|wpa'
dmesg -T | grep -iE 'brcmfmac|wlan|under-voltage|Voltage|usb|disconnect' | tail -50
```

- `dhcp4 ... new lease` が出ている → リンク／無線のやり直しが疑わしい
- 起動ログに `power save enabled` → Wi‑Fi パワーセーブが有効だった可能性

### 3. Wi‑Fi パワーセーブ（効きやすい）

```bash
# いま切る（再起動で戻ることが多い）
sudo iwconfig wlan0 power off
# または
sudo iw dev wlan0 set power_save off

# 確認
iwconfig wlan0 | grep -i power
iw dev wlan0 get power_save
```

恒久化の例（NetworkManager 利用時）:

```bash
nmcli -t -f NAME,DEVICE connection show --active
sudo nmcli connection modify '<接続名>' 802-11-wireless.powersave 2
sudo nmcli connection up '<接続名>'
iw dev wlan0 get power_save
```

（`2` = disable。環境によりキー名が違う場合あり）

### 4. スキャナ常駐・アプリログ

```bash
systemctl status scanner_service.service --no-pager
journalctl -u scanner_service.service --since "1 hour ago" --no-pager
sudo tail -n 200 /var/log/scanner/scanner.log
```

### 読み方の目安

| 兆候 | 疑い |
|------|------|
| `throttled` 非ゼロ / under-voltage | 電源不足（Hub 給電など） |
| brcmfmac disconnect / DHCP new lease | Wi‑Fi 不安定・再接続 |
| power save on | パワーセーブによる間欠切断 |
| oom-kill | メモリ不足（スキャン負荷） |
| 特に何もない | ルーター側切断や、一瞬の過負荷で SSH だけタイムアウト |

完全にハングして SSH 不能のときは、可能なら HDMI コンソールや ping、ルーター上のクライアント表示で「本体死」か「無線だけ」かを切り分ける。最終手段の電源抜きは SD カードに優しくないので、再現時は上記ログを一度残す。

----------

以上