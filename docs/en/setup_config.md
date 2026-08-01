# b4m-necromancer Setup and Configuration

## Scanner configuration (`scanner.json`)

Scanner model and device name are configured via `~/app/config/scanner.json`.

```json
{
  "device_name": "fujitsu:ScanSnap iX500:17872",
  "vendor_keyword": "fujitsu",
  "model_keyword": "ix500",
  "backend": "fujitsu",
  "default_source": "ADF Duplex",
  "test_timeout_sec": 10
}
```

- **device_name**: SANE device name shown by `scanimage -L`. Change this when you switch to a different scanner.
- **vendor_keyword**: Lowercased vendor keyword used when auto-detecting a scanner from `scanimage -L` output.  
  Examples: `fujitsu`, `brother`, `epson`, etc.
- **model_keyword**: Lowercased model keyword used together with `vendor_keyword` for auto-detection.  
  Examples: `ix500`, `fi-7160`, `dcp-c1210n`, etc.
- **backend**: SANE backend name (currently for informational purposes only).
- **default_source**: Default source used when `mode.json` has no `source` field.
- **test_timeout_sec**: Timeout (seconds) for the scanner self-test (`scanimage --device=... -n`).

#### How to find the scanner device name

1. On the Raspberry Pi, run the following in a terminal:

```bash
scanimage -L
```

Example output:

```text
device `fujitsu:ScanSnap iX500:17872' is a FUJITSU ScanSnap iX500 scanner
device `escl:http://192.168.68.109:80' is a Brother DCP-C1210N platen scanner
```

- Take the string inside `device \`...\`` (e.g. `fujitsu:ScanSnap iX500:17872`) and put it into `scanner.json`'s `device_name`.
- For network scanners (`escl:http://...`, `airscan:e0:...`), you can also copy those values directly into `device_name`.

2. Optionally, you can verify USB connectivity with `lsusb`:

```bash
lsusb
```

Example:

```text
Bus 001 Device 004: ID 04c5:132b FUJITSU LIMITED ScanSnap iX500
```

This only confirms that the scanner is physically attached; the actual value you write into `scanner.json` should come from `scanimage -L`.

3. Example settings for `vendor_keyword` / `model_keyword`

- For iX500:  
  - `vendor_keyword`: `fujitsu`  
  - `model_keyword`: `ix500`
- For a network scanner like Brother DCP-C1210N:  
  - `vendor_keyword`: `brother`  
  - `model_keyword`: `dcp-c1210n`

These keywords are matched against both the device name and the description in `scanimage -L` output.  
When you replace the physical scanner, update `device_name` plus these two keywords so that the auto-detection logic can keep working.


## Scan modes (`mode.json`)

Scan modes are configured in `~/app/config/mode.json`.  
Keypad bindings (1 → diary, etc.) are also defined here.

```json
{
  "keybindings": {
    "1": "diary",
    "2": "receipt",
    "3": "flyer"
  },
  "receipt": {
    "mode": "color",
    "resolution": 200,
    "source": "ADF Front",
    "file_format": "jpeg",
    "swcrop": true,
    "swdeskew": true,
    "max_page_height_mm": 600,
    "ald": true
  },
  "diary": {
    "mode": "color",
    "resolution": 200,
    "source": "ADF Duplex",
    "file_format": "pdf",
    "swcrop": false,
    "swdeskew": true,
    "page_width_mm": 210,
    "page_height_mm": 305,
    "blank_filter": true
  },
  "flyer": {
    "mode": "color",
    "resolution": 300,
    "source": "ADF Duplex",
    "file_format": "jpeg",
    "swcrop": false,
    "swdeskew": true,
    "max_page_height_mm": 400,
    "ald": true,
    "blank_filter": true
  }
}
```

- **keybindings**: Mapping from keypad digits to mode names (e.g. `"1": "diary"`).  
  You can change this to map key `1` to any other mode.
- **mode / resolution / file_format**: Map directly to SANE options `--mode`, `--resolution`, and the output format.
- **source**: Paper feed direction, such as `ADF Front` (simplex) or `ADF Duplex` (duplex).
- **swcrop / swdeskew**: Enable Fujitsu backend software cropping / deskewing (`--swcrop`, `--swdeskew`).
- **page_width_mm / page_height_mm**: Fixed paper size (in millimeters), useful for A4-fixed modes.
- **max_page_height_mm**: Maximum length for long paper, such as receipts, passed to `--page-height`.
- **ald**: Enable automatic length detection (`--ald=yes`), helpful for faster receipt scanning.
- **blank_filter**: When `true`, try to automatically drop almost-blank pages (e.g. flyer back sides).


## Upload configuration (`upload.json`)

Where to upload scan results is configured via `~/app/config/upload.json`.  
Currently, only `provider: "nextcloud"` is supported.

```json
{
  "provider": "nextcloud",
  "nextcloud": {
    "endpoint": "https://your-nextcloud-server.com/remote.php/dav/files/username/",
    "username": "your_username",
    "password": "your_password",
    "upload_folder": "Scans/",
    "delete_after_upload": true
  }
}
```

- **provider**: Slug for the cloud provider (currently only `"nextcloud"` is supported).
- **nextcloud**: Nextcloud-specific configuration:  
  - **endpoint**: WebDAV base URL (must end with `/`).  
  - **username / password**: Nextcloud credentials.  
  - **upload_folder**: Folder path on Nextcloud where files will be uploaded.  
  - **delete_after_upload**: Whether to delete local files/directories after a successful upload.

In the future, Dropbox or Google Drive support can be added by extending `upload.json` with another provider
and adding a corresponding adapter, without changing the scanning logic.

--------

Done.

