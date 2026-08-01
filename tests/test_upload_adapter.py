import json
from pathlib import Path

from app.lib import upload_adapter


def test_get_uploader_from_config_nextcloud(tmp_path, monkeypatch):
    cfg_path = tmp_path / "upload.json"
    cfg_path.write_text(
        json.dumps({"provider": "nextcloud", "nextcloud": {"endpoint": "x", "username": "u", "password": "p"}}),
        encoding="utf-8",
    )

    def fake_loader(config_path=str(cfg_path)):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    monkeypatch.setattr(upload_adapter, "_load_upload_config_raw", fake_loader)

    uploader = upload_adapter.get_uploader_from_config()
    assert isinstance(uploader, upload_adapter.NextcloudUploader)


def test_get_uploader_from_config_unknown_provider(tmp_path, monkeypatch, capsys):
    cfg_path = tmp_path / "upload.json"
    cfg_path.write_text(
        json.dumps({"provider": "dropbox", "nextcloud": {"endpoint": "x", "username": "u", "password": "p"}}),
        encoding="utf-8",
    )

    def fake_loader(config_path=str(cfg_path)):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    monkeypatch.setattr(upload_adapter, "_load_upload_config_raw", fake_loader)

    uploader = upload_adapter.get_uploader_from_config()
    captured = capsys.readouterr()

    assert isinstance(uploader, upload_adapter.NextcloudUploader)
    assert "unsupported provider specified: dropbox" in captured.out

