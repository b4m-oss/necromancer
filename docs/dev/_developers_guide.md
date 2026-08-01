# b4m-necromancer Developers' guide

## 目的

このプロジェクトは、公式サポートが得られなくなったスキャナを延命するためのプロジェクトです。
それ以上でもそれ以下でもありません。
開発に参加する上で、それを忘れないように心がけてくださいますよう、お願い申し上げます。



## 言語について

開発に必要なコミュニケーションにあたり、以下の言語を推奨します。

- 英語(English)
- 日本語

その他の言語は、機械翻訳にて対応します。
また、英語・日本語以外でのコミュニケーションが発生した場合、その項目は優先度が下がる場合があります。

ソースコード内のコメント、標準出力も同じです。
ただし、これらは極力英語に置き換えられていきます。
そのため、最初から英語で書いていただくのがベストです。

------

## Local development (pyproject + Docker)

- Python **3.11** (see `.python-version`).
- Root `pyproject.toml` is the source of truth for runtime and `dev` extras.
- Pi deploy path: `app/install.sh` still installs from `app/requirements.txt` into `$HOME/app/venv` (pins mirrored from `pyproject.toml`).

### Host

```bash
make install-dev
make test
make test-cov
```

`pip install -e ".[dev]"` installs Pillow and pytest extras. `evdev` installs on Linux only.

### Docker

```bash
make docker-build
make docker-test
```

The image is `python:3.11-slim-bookworm` with an editable install. It is for unit tests only (no SANE/USB / Pi runtime).

------

以上
