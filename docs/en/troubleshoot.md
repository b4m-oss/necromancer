# b4m-necromancer Troubleshooting

## Check service status

```bash
sudo systemctl status scanner_service.service
```

## Check logs

```bash
tail -f /var/log/scanner/scanner.log
```

## Run scripts manually

```bash
# Interactive mode (run the installed ~/app directly)
python3 ~/app/keypad_scanner.py

# Daemon-like mode
python3 ~/app/keypad_daemon.py
```

## Specify device path

If you want to use a specific keypad device:

```bash
python3 ~/app/keypad_daemon.py --device /dev/input/event0
```

## Slow or intermittent SSH / network

On a Raspberry Pi Zero 2 W, the board may stay up while Wi‑Fi drops and SSH works again after a few minutes (more like wireless reconnect than deep sleep). USB-hub power can also cause brownouts.

Right after you regain SSH, check the following.

### 1. Power / throttling

```bash
vcgencmd get_throttled
vcgencmd measure_volts
```

- `throttled=0x0` — no power/thermal throttle flags right now
- Non-zero — possible under-voltage (prefer a wall 5V PSU over hub power)
- `measure_volts` is the SoC core voltage, not the USB 5V rail

### 2. Wi‑Fi / DHCP logs

```bash
journalctl --since "1 hour ago" --no-pager | grep -iE 'wlan|brcmfmac|wifi|dhcp|disconnect|associate|NetworkManager|wpa'
dmesg -T | grep -iE 'brcmfmac|wlan|under-voltage|Voltage|usb|disconnect' | tail -50
```

- `dhcp4 ... new lease` — link/Wi‑Fi may have renegotiated
- Boot log `power save enabled` — Wi‑Fi power save was on

### 3. Disable Wi‑Fi power save (often helps)

```bash
# Temporary (often resets on reboot)
sudo iwconfig wlan0 power off
# or
sudo iw dev wlan0 set power_save off

# Verify
iwconfig wlan0 | grep -i power
iw dev wlan0 get power_save
```

Persist with NetworkManager (example):

```bash
nmcli -t -f NAME,DEVICE connection show --active
sudo nmcli connection modify '<connection-name>' 802-11-wireless.powersave 2
sudo nmcli connection up '<connection-name>'
iw dev wlan0 get power_save
```

(`2` = disable; key names may vary by environment.)

### 4. Scanner service / app logs

```bash
systemctl status scanner_service.service --no-pager
journalctl -u scanner_service.service --since "1 hour ago" --no-pager
sudo tail -n 200 /var/log/scanner/scanner.log
```

### Quick interpretation

| Symptom | Suspect |
|---------|---------|
| Non-zero `throttled` / under-voltage | Weak power (e.g. USB hub) |
| brcmfmac disconnect / DHCP new lease | Wi‑Fi blip / reconnect |
| power save on | Intermittent disconnect from power save |
| oom-kill | Memory pressure during scan |
| Nothing obvious | Router-side drop or brief load; SSH timed out |

If the Pi is fully hung, use HDMI console, ping, or the router client list to tell “dead board” vs “Wi‑Fi only”. Hard power-cycles wear the SD card; capture the logs above when it happens again.

----------

Done.

