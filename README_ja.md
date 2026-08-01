# b4m-necromancer - revive your old scanner with Raspberry Pi ZERO 2

[English](./README.md)

このシステムは、テンキーパッドからの入力によってドキュメントスキャンを自動実行するためのソリューションです。
テンキーの数字を押してEnterを押すだけで、異なるモードでのスキャンが可能です。

## モチベーション

メーカーサポートの切れたスキャナを、OSSの力を使って蘇らせる。

開発者は、FujitsuのiX500を使っていましたが、ある時、iOSアプリのサポートが打ち切られました。
どうしてもWiFi下でリモートにファイルをアップデートしたかったため、様々な方策を考えました。
結果、SANEというライブラリを見つけ、これをRaspberry Pi ZERO 2で動かすことを思いついたのです。

## 何ができますか？

- サポートの切れたスキャナを継続して使用することができます
- 自動でクラウドサービスにスキャンした内容をアップロードすることができます
- 細かな設定を自分でプリセットとして用意することができます
- テンキー入力から操作を実行できます

## 必要なハードウェア

- Raspberry Pi Zero 2W（または他のRaspberry Pi）
- ScanSnap iX500スキャナー（または他のSANE対応スキャナー）
- テンキーパッド（USBまたはBluetooth接続）

## 機能

- テンキーパッドからの入力を監視
- 数字キーごとに異なるスキャンモードを実行（diary、receipt、flyer）
- スキャンした文書をNextcloudに自動アップロード
- システム起動時に自動的にサービス開始
- ログ出力による動作記録


## インストール方法

### 自動インストール

以下では、リポジトリを `~/b4m-necromancer` にクローンする前提で説明します。

1. Raspberry Pi 上でリポジトリをクローンします
2. `app` ディレクトリに移動してインストールスクリプトを実行します

```bash
git clone https://github.com/b4m-oss/b4m-necromancer.git ~/b4m-necromancer
cd ~/b4m-necromancer/app
chmod +x install.sh
./install.sh
```

### 手動インストール

[手動インストール](./docs/ja/manual_installation.md)を参照して下さい。

## セットアップと設定

[セットアップと設定](./docs/ja/setup_config.md)を参照して下さい。

## 使い方

システムを起動すると、テンキーパッドの監視が自動的に開始されます。以下の操作でスキャンを実行できます：

1. テンキーの「1」→ Enter：`mode.json` の `keybindings["1"]` で指定されたモード（デフォルト: diary）でスキャン
2. テンキーの「2」→ Enter：`keybindings["2"]` のモード（デフォルト: receipt）でスキャン
3. テンキーの「3」→ Enter：`keybindings["3"]` のモード（デフォルト: flyer）でスキャン

数字キーを押してから5秒以内にEnterを押さない場合、入力はクリアされます。また、別の数字キーを押すと入力は上書きされます。

### コンフィグダンプ (`--dump-config`)

本番スキャンの前に、**「最終的にどのコマンド・どのクラウドパスで動くか」** を確認したい場合は、`--dump-config` オプションを使います。

- 読み込まれる設定:
  - `app/config/scanner.json`
  - `app/config/mode.json`
  - `app/config/upload.json`
- ダンプ内容:
  - 実際に `scanimage` に渡されるバッチスキャン用コマンドライン
  - スキャン結果のアップロード先情報（プロバイダ／エンドポイント／アップロードフォルダ／リモートパスのパターン など）

#### 使い方

開発環境から直接実行する場合:

```bash
python3 -m app.lib.scan --dump-config diary
```

インストール済みの環境では、`install.sh` により `necro` エイリアスがシェルに追加されるため、次のようにも実行できます（新しいシェルを開くか、`source ~/.bashrc` / `source ~/.zshrc` を実行してから利用してください）。

```bash
necro --dump-config diary
```

#### 出力イメージ（抜粋）

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

- 実際の `{timestamp}` には実行時のタイムスタンプが入ります。
- **注意:** `--dump-config` は設定を計算して表示するだけで、スキャンやアップロードは行いません（ドライに確認できます）。

## ローカル開発（ホスト / Docker）

依存関係はルートの `pyproject.toml` に定義しています（`requires-python >=3.11`）。  
Raspberry Pi 向けインストールは従来どおり `app/install.sh` が `app/requirements.txt` を使います（ランタイムのピンは `pyproject.toml` と同期）。

### ホスト（Python 3.11）

```bash
make install-dev   # .venv を作成し pip install -e ".[dev]"
make test
make test-cov
```

macOS では `evdev` はスキップされます（Linux 向けマーカー）。テストは既存の fake/mock を使います。

### Docker（Python 3.11 固定）

```bash
make docker-build
make docker-test
```

Compose / `docker run` の例:

```bash
docker compose build
docker compose run --rm dev
docker run --rm -v "$PWD":/workspace -w /workspace b4m-necromancer-dev:3.11   sh -c "pip install -q -e '.[dev]' && pytest -q"
```

詳細は [開発者ガイド](./docs/dev/_developers_guide.md) を参照してください。

## サポート

**おことわり**
このプロダクトは、一切のサポートがありません。
このプロダクトを用いて、ユーザーに損害が発生した場合、開発者は一切の責任を負いません。
ユーザーがこのプロダクトを利用するときは、それに承諾したものとします。

### 有償サポート

他のスキャナへの対応、他のクラウドストレージへの対応といったカスタマイズは、有償にて行います。
[合同会社 知的・自転車](https://b4m.co.jp/)まで、お問い合わせください。

## トラブルシューティング

[トラブルシューティング](./docs/ja/troubleshoot.md)を参照して下さい。

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。詳細はLICENSEファイルを参照してください。 


-------------

Developed by Kohki SHIKATA / B4M LLC. from Osaka with ❤️