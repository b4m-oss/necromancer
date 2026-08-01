# LED インジケータ追加 設計メモ

本ドキュメントは、b4m-necromancer に「LED による状態表示」を追加する際の、ざっくりとした方針メモです。  
現時点では実装は行わず、アイデアレベル・設計レベルの整理だけを行います。

---

## 1. 目的・ユースケース

- Raspberry Pi ZERO 2 W 本体やケースに小型 LED を取り付け、
  - **daemon が動作中かどうか**
  - **スキャンの進行状況**
  - **エラー発生有無**
  などを、RPi 本体側だけで把握できるようにする。
- 具体的な想定:
  - 起動時: 短い点滅パターンで「daemon 起動 OK」を示す。
  - 待機中: 点灯 or ゆっくり点滅（「待機中・ready」）。
  - スキャン中: 速い点滅（「処理中」）。
  - 正常終了: 一定パターン（2回チカチカ等）で成功を示す。
  - エラー: 別パターン（長い点滅＋回数など）でエラーを示す。

---

## 2. ハードウェア方針（ふわっと案）

- RPi の GPIO に直接 LED を接続する前提。
  - 例: 汎用 5mm LED + 抵抗（330Ω〜1kΩ 程度） + ブレッドボード or 基板。
  - GPIO 番号は設定ファイルで変更可能にする（デフォルト値はひとつ決める）。
- 単色 LED（1本）のみを扱う前提で設計。
  - 将来的に RGB LED に拡張できるよう、コード側では「状態 → 抽象化された LED パターン」にマッピングする層を置く。

※ どの GPIO を使うか、どの色の LED を使うか等は、実装時に詰める（**未確定**）。

---

## 3. ソフトウェア設計方針

### 3.1 LED 制御モジュール

- 例: `app/lib/led_indicator.py` を新設。
- 役割:
  - GPIO へのアクセスを一箇所にまとめる。
  - `set_state("idle")`, `set_state("scanning")`, `set_state("error")` のような API を提供。
  - 内部でスレッドを用いて点滅パターンを制御する（メイン処理をブロックしない）。

```python
class LedIndicator:
    def __init__(self, gpio_pin: int):
        ...

    def set_state(self, state: str) -> None:
        # state: "boot", "idle", "scanning", "success", "error"
        ...

    def shutdown(self) -> None:
        ...
```

### 3.2 連携ポイント

- `keypad_daemon.py` 側で LED を初期化し、以下のタイミングで状態を変更:
  - daemon 起動直後: `set_state("boot")`
  - キーパッド監視開始後（正常待機状態）: `set_state("idle")`
  - スキャン開始: `set_state("scanning")`
  - スキャン正常終了: `set_state("success")` → 少し時間をおいて `set_state("idle")`
  - スキャンエラー時: `set_state("error")` → 一定時間後に `set_state("idle")`（or ユーザが気付くまで error のまま）
- 可能であれば、Nextcloud 等のアップロード成功 / 失敗も反映する（**詳細なタイミングは実装時検討**）。

---

## 4. 設定ファイルとの連携（イメージ）

- 将来的に `~/app/config/device.json` のような設定ファイルを新設し、  
  LED 関連の設定を持たせる案:

```json
{
  "led": {
    "enabled": true,
    "gpio_pin": 18,
    "active_high": true
  }
}
```

- あるいは既存の `scanner.json` / `mode.json` とは分けて、ハードウェア周り専用の `hardware.json` などにまとめることも検討（**未確定**）。

---

## 5. 実装ステップ案（まだ着手しない）

1. LED ハードウェア（LED + 抵抗 + 配線）を物理的に用意し、GPIO ピン番号を確定。
2. `led_indicator.py`（仮）を実装し、スタンドアロンで点灯・点滅テストができるようにする。
3. `keypad_daemon.py` から LED を初期化・状態遷移させる実験コードを入れる（最初はハードコードでも可）。
4. 問題なく動作したら、GPIO ピン番号等を設定ファイル経由に切り出し、ハード依存部分を緩くする。
5. README / docs に「LED 対応（任意）」として配線図・設定例を追記。

現時点ではここまでをメモとして残し、実装は将来のタスクとする。

