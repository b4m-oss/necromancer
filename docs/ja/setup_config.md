# b4m-necromancer セットアップと設定

## スキャナ設定（`scanner.json`）

スキャナ本体の種類やデバイス名は `~/app/config/scanner.json` で設定します。

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

- **device_name**: `scanimage -L` で表示される SANE デバイス名。別のスキャナに差し替える場合はここを変更します。
- **vendor_keyword**: `scanimage -L` の出力からスキャナを自動検出する際に使うベンダー名キーワード（小文字）。  
  例: `fujitsu`, `brother`, `epson` など。
- **model_keyword**: 同じく自動検出に使うモデル名キーワード（小文字）。  
  例: `ix500`, `fi-7160`, `dcp-c1210n` など。
- **backend**: 使用する SANE バックエンド名（現在は情報用途）。
- **default_source**: `mode.json` に `source` が無い場合のデフォルトソース。
- **test_timeout_sec**: スキャナー診断 (`scanimage --device=... -n`) のタイムアウト秒数。

#### スキャナのデバイス名を調べる方法

1. Raspberry Pi 上で、ターミナルから以下を実行します。

```bash
scanimage -L
```

出力例:

```text
device `fujitsu:ScanSnap iX500:17872' is a FUJITSU ScanSnap iX500 scanner
device `escl:http://192.168.68.109:80' is a Brother DCP-C1210N platen scanner
```

- `device \`...\`` の中身（例: `fujitsu:ScanSnap iX500:17872`）をそのまま `scanner.json` の `device_name` に設定します。
- ネットワークスキャナの場合も同様に、`escl:http://...` や `airscan:e0:...` の行を `device_name` に指定します。

2. 必要であれば、USB 接続の確認に `lsusb` も使えます。

```bash
lsusb
```

出力例:

```text
Bus 001 Device 004: ID 04c5:132b FUJITSU LIMITED ScanSnap iX500
```

これは「Pi に物理的に刺さっているか」の確認用で、実際に `scanner.json` に書く値は `scanimage -L` の結果を使います。

3. `vendor_keyword` / `model_keyword` の設定例

- iX500 の場合:  
  - `vendor_keyword`: `fujitsu`  
  - `model_keyword`: `ix500`
- Brother DCP-C1210N のようなネットワークスキャナの場合:  
  - `vendor_keyword`: `brother`  
  - `model_keyword`: `dcp-c1210n`

これらのキーワードは、`scanimage -L` の出力中のどこかに含まれていればマッチします。  
新しいスキャナに差し替えた場合も、`device_name` と合わせてこの 2 つを更新することで、自動検出ロジックが追随します。


## スキャンモードの設定（`mode.json`）

スキャンモードは `~/app/config/mode.json` ファイルで設定できます。  
テンキーとの対応（1→diary など）もここで定義します。

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

- **keybindings**: テンキーの数字とモード名の対応（例: `"1": "diary"`）。変更すれば、テンキー1で別モードを起動させることもできます。
- **mode / resolution / file_format**: SANE の `--mode` / `--resolution` / 出力フォーマットに対応します。
- **source**: 用紙の投入方向。`ADF Front`（片面）/`ADF Duplex`（両面）など。
- **swcrop / swdeskew**: SANE Fujitsu backend のソフトウェアクロップ／傾き補正（`--swcrop` / `--swdeskew`）を有効にします。
- **page_width_mm / page_height_mm**: mm 単位で用紙サイズを指定することで、A4 固定などに使えます。
- **max_page_height_mm**: レシートのような長尺紙の最大長（mm）。`--page-height` に渡されます。
- **ald**: 自動長さ検出（`--ald=yes`）を有効にします。レシートモードで高速化に効きます。
- **blank_filter**: `true` のモードでは、スキャン後に「ほぼ白いページ」を自動的に削除しようと試みます（flyer 裏面など）。



## アップロード設定（`upload.json`）

スキャン結果をどのクラウドにアップロードするかは `~/app/config/upload.json` で設定します。  
現時点では `provider: "nextcloud"` のみサポートしています。

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

- **provider**: 利用するクラウド種別をスラッグで指定します（現状 `\"nextcloud\"` のみ）。
- **nextcloud**: Nextcloud 用の詳細設定。  
  - **endpoint**: WebDAV のベース URL（必ず末尾に `/` を付ける）。  
  - **username / password**: Nextcloud の認証情報。  
  - **upload_folder**: Nextcloud 内でアップロード先とするフォルダパス。  
  - **delete_after_upload**: アップロード完了後にローカルファイル／ディレクトリを削除するかどうか。

今後 Dropbox や Google Drive などに対応する場合も、`upload.json` の `provider` を切り替え、  
各クラウド向けセクションを追加するだけで済む想定です。

--------

以上