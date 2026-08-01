# 結合テスト / E2E テスト計画（b4m-necromancer）

このドキュメントは、b4m-necromancer の **結合テスト／フル E2E テスト** をどのレイヤーで、どのような観点で行うかをまとめたものです。  
pytest ベースの「単体テスト（ユニットテスト）」を補完する形で、**実際のサービス・実機を組み合わせたテスト**の指針を定義します。

---

## 1. レイヤー構成

結合〜E2E テストは、次の 3 レイヤーで考える。

1. **クラウド連携レイヤー**  
   - 対象: `app/lib/nextcloud.py`  
   - Nextcloud 実サービスを相手に、「設定 → HTTP 通信 → 実ファイルがアップロードされるか」を確認。

2. **スキャン処理レイヤー（RasPi + iX500）**  
   - 対象: `app/lib/scan.py`  
   - Raspberry Pi + ScanSnap iX500 で、実際に紙を読み込み、ローカルに JPEG / PDF が生成されるかを確認。

3. **フル E2E レイヤー（テンキー → daemon → scan → Nextcloud）**  
   - 対象: `keypad_daemon.py` / `scan.py` / `nextcloud.py` / systemd サービス  
   - テンキーからのキー入力をトリガに、「スキャン〜アップロード」までの実運用フロー全体を確認。

ユニットテスト（pytest）は「コード単体の正しさ」を見るのに対し、  
本ドキュメントで扱うテストは「**コード＋実サービス＋実機**の組み合わせで問題なく動くか」を確認することが目的。

---

## 2. クラウド連携レイヤー（Nextcloud 実機テスト）

### 2.1 目的

- `upload.json` の設定が正しく解釈され、  
  Nextcloud の WebDAV API に対して **実際にファイルがアップロードできること**を確認する。
- HTTP 2xx / エラー時の挙動（ローカルファイルの削除可否など）が仕様通りであることを確認する。

### 2.2 前提準備

- Nextcloud 側にテスト用アカウントを作成する（例: `test-b4m`）。
- テスト用アップロードフォルダ（例: `TestScans/`）を用意する。
- Mac もしくは RasPi 上で、`app/config/upload.json` をテスト用アカウントに差し替える:

```json
{
  "provider": "nextcloud",
  "nextcloud": {
    "endpoint": "https://your-nextcloud-server.com/remote.php/dav/files/test-b4m/",
    "username": "test-b4m",
    "password": "********",
    "upload_folder": "TestScans/",
    "delete_after_upload": false
  }
}
```

※ 本番用アカウントとは別にしておくとテストがやりやすい。

### 2.3 テスト観点（例）

#### 2.3.1 単一ファイルアップロード

- 手順
  1. ローカルに小さなテキストファイル `test.txt` を作成する。
  2. Python シェルまたは簡易スクリプトから `upload_file_to_nextcloud("test.txt")` を呼ぶ。
  3. Nextcloud の Web UI あるいは `curl -I` で `TestScans/test.txt` の存在を確認する。
- 条件
  - HTTP ステータスが 2xx であること。
  - ファイル内容がローカルと一致すること（必要であればダウンロードして比較）。

#### 2.3.2 ディレクトリアップロード

- 手順
  1. ローカルに `testDir/` を作り、`a.jpg`, `b.jpg` を配置する。
  2. `upload_directory_to_nextcloud("testDir")` を呼ぶ。
  3. Nextcloud 側に `TestScans/testDir/` が作られ、`a.jpg`, `b.jpg` が存在することを確認する。
- 条件
  - サブディレクトリ名がローカルの `testDir` に対応していること。
  - すべてのファイルがアップロードされていること。

#### 2.3.3 PDF アップロード ＋ 削除（delete_after_upload）

- 手順
  1. ローカルにダミー PDF `dummy.pdf` を作成する。
  2. `upload_pdf_to_nextcloud("dummy.pdf", delete_after_upload=True)` を呼ぶ。
  3. 呼び出し後、ローカルから `dummy.pdf` が削除されていることを確認する。
  4. Nextcloud 側で `TestScans/dummy.pdf` が存在することを確認する。
- 条件
  - アップロード成功時のみローカル削除されること（失敗時はローカルに残ること）。

---

## 3. スキャン処理レイヤー（RasPi + iX500）

### 3.1 目的

- Raspberry Pi + ScanSnap iX500 の実機環境で、
  - `scan.py` によるスキャン実行
  - JPEG / PDF ファイル生成
  が **現実の紙に対して期待通り動作すること**を確認する。
- モード別（diary / receipt / flyer）の画角・余白・長さ制御が設計通りであるかを確認する。

### 3.2 前提準備

- RasPi 上に本プロジェクトを配置し、`install.sh` 相当のセットアップを完了しておく。
- `scan.py` がコマンドラインから呼べる状態にする:

```bash
cd ~/app
python3 lib/scan.py --list              # スキャナ一覧確認
python3 lib/scan.py diary --no-upload   # diary モード試験
python3 lib/scan.py receipt --no-upload # receipt モード試験
python3 lib/scan.py flyer --no-upload   # flyer モード試験
```

※ `--no-upload` を付けることで Nextcloud 連携を切り、スキャン〜ファイル生成のみに絞る。

### 3.3 テスト観点（例）

#### 3.3.1 diary モード（A4 固定）の画角確認

- 手順
  1. A4 用紙に枠線などを描いた「テストシート」を用意する。
  2. RasPi から `python3 lib/scan.py diary --no-upload` を実行する。
  3. 生成された `tmp/<timestamp>/diary-1.jpg` または PDF を Mac に転送し、画像を確認する。
- 観点
  - A4 の縦横比に近いクロップになっているか。
  - 上下左右の余白が「想定どおりの安全側」になっているか。

#### 3.3.2 receipt モード（レシート長さ検出）

- 手順
  1. 短いレシート・中くらいの長さ・長めのレシートを数枚用意する。
  2. `python3 lib/scan.py receipt --no-upload` を実行し、複数パターンをスキャンする。
  3. 生成された画像／PDF を確認する。
- 観点
  - 上下端が途中で切れていないか。
  - 長いレシートでも指定上限（例: 600mm）内で問題なく収まっているか。
  - スキャンの待ち時間が実用上許容できるレベルか（純正アプリと比較した体感）。

#### 3.3.3 flyer モード（余白許容）

- 手順
  1. カラー印刷のチラシ、白背景多めのチラシなど複数パターンを用意する。
  2. `python3 lib/scan.py flyer --no-upload` を実行し、それぞれスキャンする。
  3. 生成された画像／PDF を確認する。
- 観点
  - 末端が切れずに「安全寄り」のクロップになっているか。
  - 白紙混入時、blank_filter の設定どおりに残す／落とす挙動になっているか（運用方針に合わせる）。

---

## 4. フル E2E レイヤー（テンキー → daemon → scan → Nextcloud）

### 4.1 目的

- 本番運用とほぼ同じ構成で、
  - テンキー入力
  - systemd サービスとしての `keypad_daemon.py`
  - `scan.py` によるスキャン
  - `nextcloud.py` 経由でのアップロード
  が一連の流れとして正常に動作することを確認する。
- エラー発生時にも daemon が落ちず、次回以降のスキャンが継続できることを確認する。

### 4.2 前提準備

- RasPi 上で `scanner_service.service` を有効化し、再起動時に自動起動する状態にしておく。
- テスト用の Nextcloud フォルダを決め、`upload.json` の `upload_folder` をそこで運用する:
  - 例: `E2E/2026-XX-YY/`

### 4.3 テスト観点（例）

#### 4.3.1 モード別 E2E 動作確認

- 手順（例）
  1. RasPi とテンキー、ScanSnap iX500 を通常どおり接続する。
  2. daemon が起動していることを `systemctl status scanner_service` などで確認する。
  3. テンキーで `1` → Enter（diary）、`2` → Enter（receipt）、`3` → Enter（flyer）を順に試す。
  4. Nextcloud 側の `E2E/yyyymmdd.../` 以下に各モードごとのファイルができていることを確認する。
- 観点
  - 期待するモード名（diary / receipt / flyer）に対応した設定でスキャンされているか。
  - エラーなく Nextcloud にアップロードされているか。

#### 4.3.2 スキャナ未接続時の挙動

- 手順
  1. ScanSnap iX500 の電源を OFF にした状態でテンキーからスキャンを発火する。
  2. `/var/log/scanner/scanner.log` を確認する。
- 観点
  - ログに「スキャナが見つからない」旨のメッセージが出力されていること。
  - daemon プロセス自体は落ちておらず、iX500 の電源を入れて再試行すると復帰すること。

#### 4.3.3 Nextcloud 側エラー時の挙動

- 手順
  1. 一時的に `upload.json` のパスワードを誤った値にする。
  2. テンキーからスキャンを発火する。
  3. ローカルの tmp ディレクトリ内の JPEG/PDF とログを確認する。
- 観点
  - スキャン自体は成功し、ローカル tmp ディレクトリにファイルが残ること。
  - Nextcloud アップロードのみが失敗し、ログに HTTP エラーの情報が記録されていること。
  - daemon プロセス自体は継続しており、`upload.json` を正しい値に戻せば次回以降は正常にアップロードされること。

---

## 5. 実行頻度と運用方針

- **ユニットテスト（pytest）**
  - 開発中は頻繁に実行する（小さな修正ごとに `pytest` / `pytest --cov`）。

- **クラウド連携レイヤー**
  - Nextcloud 側の設定を変えたときや、`nextcloud.py` を大きく変更したときに実行。
  - 定期的（例: 月 1 回）なヘルスチェックとしても有用。

- **スキャン処理レイヤー（RasPi + iX500）**
  - `scan.py` のオプションや `mode.json` の大きな変更時に実施。
  - ハードウェア構成を変えた（別のスキャナに乗り換えた）ときにも必須。

- **フル E2E レイヤー**
  - 大きな機能追加（例: 新モード追加、クラウド先追加）後のリリース前チェックとして実行。
  - 実運用の安定性のため、半年〜1 年に一度程度の「総点検」として回すのも良い。

---

## 6. 今後の拡張余地

- Nextcloud 以外のクラウド（Dropbox / Google Drive）対応を行った場合、
  - ここで定義した「クラウド連携レイヤー」のテスト手順を各プロバイダ向けにコピーしつつ、
  - OAuth フローや API 制限（rate limit）を踏まえたテストケースを追加する。
- LED / ブザー対応後は、
  - スキャン成功時／エラー時に正しいパターンで点灯・鳴動するかどうかを  
    フル E2E の一部として確認するテストケースを追記する。

