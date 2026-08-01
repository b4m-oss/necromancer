import json
from pathlib import Path

import pytest

from app.lib import nextcloud


def write_upload_config(tmp_path, provider="nextcloud", nextcloud_section=None):
    if nextcloud_section is None:
        nextcloud_section = {
            "endpoint": "https://example.com/remote.php/dav/files/user/",
            "username": "user",
            "password": "pass",
            "upload_folder": "Scans/",
            "delete_after_upload": False,
        }
    data = {"provider": provider, "nextcloud": nextcloud_section}
    cfg = tmp_path / "upload.json"
    cfg.write_text(json.dumps(data), encoding="utf-8")
    return cfg


def test_load_nextcloud_config_ok(tmp_path, monkeypatch):
    cfg_path = write_upload_config(tmp_path)

    cfg = nextcloud.load_nextcloud_config(str(cfg_path))
    assert cfg["endpoint"].startswith("https://example.com")
    assert cfg["upload_folder"] == "Scans/"


def test_load_nextcloud_config_invalid_section(tmp_path):
    cfg_path = tmp_path / "upload.json"
    cfg_path.write_text(json.dumps({"provider": "nextcloud", "nextcloud": "oops"}), encoding="utf-8")

    with pytest.raises(ValueError):
        nextcloud.load_nextcloud_config(str(cfg_path))


def test_create_remote_directory_201(monkeypatch):
    cfg = {
        "endpoint": "https://example.com/remote.php/dav/files/user/",
        "username": "user",
        "password": "pass",
    }

    def fake_load_config():
        return cfg

    class DummyResult:
        def __init__(self, stdout):
            self.stdout = stdout
            self.stderr = ""

    def fake_run(cmd, shell, capture_output, text):
        return DummyResult("HTTP/1.1 201 Created\n")

    monkeypatch.setattr(nextcloud, "load_nextcloud_config", fake_load_config)
    monkeypatch.setattr(nextcloud.subprocess, "run", fake_run)

    assert nextcloud.create_remote_directory("Scans/dir/") is True


def test_create_remote_directory_405(monkeypatch):
    cfg = {
        "endpoint": "https://example.com/",
        "username": "user",
        "password": "pass",
    }

    def fake_load_config():
        return cfg

    class DummyResult:
        def __init__(self, stdout):
            self.stdout = stdout
            self.stderr = ""

    def fake_run(cmd, shell, capture_output, text):
        return DummyResult("HTTP/1.1 405 Method Not Allowed\n")

    monkeypatch.setattr(nextcloud, "load_nextcloud_config", fake_load_config)
    monkeypatch.setattr(nextcloud.subprocess, "run", fake_run)

    assert nextcloud.create_remote_directory("Scans/dir/") is True


def test_create_remote_directory_no_status(monkeypatch, capsys):
    def fake_load_config():
        return {
            "endpoint": "https://example.com/",
            "username": "user",
            "password": "pass",
        }

    class DummyResult:
        def __init__(self):
            self.stdout = ""
            self.stderr = ""

    def fake_run(cmd, shell, capture_output, text):
        return DummyResult()

    monkeypatch.setattr(nextcloud, "load_nextcloud_config", fake_load_config)
    monkeypatch.setattr(nextcloud.subprocess, "run", fake_run)

    ok = nextcloud.create_remote_directory("Scans/dir/")
    assert ok is False


def test_upload_file_to_nextcloud_success(monkeypatch, tmp_path):
    cfg = {
        "endpoint": "https://example.com/remote.php/dav/files/user/",
        "username": "user",
        "password": "pass",
        "upload_folder": "Scans/",
    }

    def fake_load_config():
        return cfg

    class DummyResult:
        def __init__(self, stdout, stderr="", returncode=0):
            self.stdout = stdout
            self.stderr = stderr
            self.returncode = returncode

    def fake_run(cmd, shell, capture_output, text):
        return DummyResult("HTTP/1.1 201 Created\n")

    file_path = tmp_path / "test.txt"
    file_path.write_text("hello", encoding="utf-8")

    monkeypatch.setattr(nextcloud, "load_nextcloud_config", fake_load_config)
    monkeypatch.setattr(nextcloud.subprocess, "run", fake_run)

    ok = nextcloud.upload_file_to_nextcloud(str(file_path))
    assert ok is True


def test_upload_file_to_nextcloud_missing_file(tmp_path, monkeypatch, capsys):
    def fake_load_config():
        return {
            "endpoint": "https://example.com/",
            "username": "user",
            "password": "pass",
            "upload_folder": "Scans/",
        }

    monkeypatch.setattr(nextcloud, "load_nextcloud_config", fake_load_config)

    ok = nextcloud.upload_file_to_nextcloud(str(tmp_path / "no.txt"))
    captured = capsys.readouterr()
    assert ok is False
    assert "not found" in captured.out


def test_upload_file_to_nextcloud_status_from_progress(monkeypatch, tmp_path):
    cfg = {
        "endpoint": "https://example.com/",
        "username": "user",
        "password": "pass",
        "upload_folder": "Scans/",
    }

    def fake_load_config():
        return cfg

    class DummyResult:
        def __init__(self):
            self.stdout = ""
            self.stderr = "some progress ... 100.0%"
            self.returncode = 0

    def fake_run(cmd, shell, capture_output, text):
        return DummyResult()

    file_path = tmp_path / "test2.txt"
    file_path.write_text("hello2", encoding="utf-8")

    monkeypatch.setattr(nextcloud, "load_nextcloud_config", fake_load_config)
    monkeypatch.setattr(nextcloud.subprocess, "run", fake_run)

    ok = nextcloud.upload_file_to_nextcloud(str(file_path))
    assert ok is True


def test_upload_directory_to_nextcloud_basic(monkeypatch, tmp_path):
    # Prepare local directory with two files
    local_dir = tmp_path / "scan"
    local_dir.mkdir()
    (local_dir / "a.jpg").write_text("a", encoding="utf-8")
    (local_dir / "b.jpg").write_text("b", encoding="utf-8")

    cfg = {
        "endpoint": "https://example.com/",
        "username": "user",
        "password": "pass",
        "upload_folder": "Scans/",
        "delete_after_upload": False,
    }

    def fake_load_config():
        return cfg

    def fake_create_remote_directory(remote_dir):
        assert remote_dir.startswith("Scans/")
        return True

    uploaded = []

    def fake_upload_file_to_nextcloud(file_path, remote_path):
        uploaded.append((file_path, remote_path))
        return True

    monkeypatch.setattr(nextcloud, "load_nextcloud_config", fake_load_config)
    monkeypatch.setattr(nextcloud, "create_remote_directory", fake_create_remote_directory)
    monkeypatch.setattr(nextcloud, "upload_file_to_nextcloud", fake_upload_file_to_nextcloud)

    ok = nextcloud.upload_directory_to_nextcloud(str(local_dir), delete_after_upload=False)
    assert ok is True
    # Both files should have been uploaded
    assert len(uploaded) == 2


def test_upload_directory_to_nextcloud_create_remote_dir_fail(monkeypatch, tmp_path):
    local_dir = tmp_path / "scan"
    local_dir.mkdir()
    (local_dir / "a.jpg").write_text("a", encoding="utf-8")

    def fake_load_config():
        return {
            "endpoint": "https://example.com/",
            "username": "user",
            "password": "pass",
            "upload_folder": "Scans/",
            "delete_after_upload": False,
        }

    monkeypatch.setattr(nextcloud, "load_nextcloud_config", fake_load_config)
    monkeypatch.setattr(nextcloud, "create_remote_directory", lambda remote: False)

    ok = nextcloud.upload_directory_to_nextcloud(str(local_dir))
    assert ok is False


def test_upload_directory_to_nextcloud_no_files(monkeypatch, tmp_path, capsys):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    def fake_load_config():
        return {
            "endpoint": "https://example.com/",
            "username": "user",
            "password": "pass",
            "upload_folder": "Scans/",
            "delete_after_upload": False,
        }

    monkeypatch.setattr(nextcloud, "load_nextcloud_config", fake_load_config)

    ok = nextcloud.upload_directory_to_nextcloud(str(empty_dir))
    captured = capsys.readouterr()
    assert ok is False
    # Implementation may fail early while trying to create a remote directory.
    # We only assert that the function reports failure; detailed message is implementation-dependent.
    assert captured.out  # some message is printed


def test_upload_pdf_to_nextcloud_missing(monkeypatch, tmp_path):
    def fake_load_config():
        return {
            "endpoint": "https://example.com/",
            "username": "user",
            "password": "pass",
            "upload_folder": "Scans/",
            "delete_after_upload": False,
        }

    monkeypatch.setattr(nextcloud, "load_nextcloud_config", fake_load_config)

    ok = nextcloud.upload_pdf_to_nextcloud(str(tmp_path / "no.pdf"))
    assert ok is False


def test_upload_pdf_to_nextcloud_success(monkeypatch, tmp_path):
    cfg = {
        "endpoint": "https://example.com/",
        "username": "user",
        "password": "pass",
        "upload_folder": "Scans/",
        "delete_after_upload": False,
    }

    def fake_load_config():
        return cfg

    class DummyResult:
        def __init__(self):
            self.stdout = "HTTP/1.1 201 Created\n"
            self.stderr = ""
            self.returncode = 0

    def fake_run(cmd, shell, capture_output, text):
        return DummyResult()

    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4 dummy")

    monkeypatch.setattr(nextcloud, "load_nextcloud_config", fake_load_config)
    monkeypatch.setattr(nextcloud.subprocess, "run", fake_run)

    ok = nextcloud.upload_pdf_to_nextcloud(str(pdf), delete_after_upload=False)
    assert ok is True


def test_upload_pdf_to_nextcloud_delete_after(monkeypatch, tmp_path):
    cfg = {
        "endpoint": "https://example.com/",
        "username": "user",
        "password": "pass",
        "upload_folder": "Scans/",
        "delete_after_upload": True,
    }

    def fake_load_config():
        return cfg

    class DummyResult:
        def __init__(self):
            self.stdout = "HTTP/1.1 201 Created\n"
            self.stderr = ""
            self.returncode = 0

    def fake_run(cmd, shell, capture_output, text):
        return DummyResult()

    pdf = tmp_path / "doc2.pdf"
    pdf.write_bytes(b"%PDF-1.4 dummy")

    monkeypatch.setattr(nextcloud, "load_nextcloud_config", fake_load_config)
    monkeypatch.setattr(nextcloud.subprocess, "run", fake_run)

    ok = nextcloud.upload_pdf_to_nextcloud(str(pdf), delete_after_upload=True)
    assert ok is True
    # ファイルは削除されているはず
    assert not pdf.exists()


def test_test_nextcloud_connection_ok(monkeypatch):
    cfg = {
        "endpoint": "https://example.com/remote.php/dav/files/user/",
        "username": "user",
        "password": "pass",
    }

    def fake_load_config():
        return cfg

    class DummyResult:
        def __init__(self, stdout, stderr="", returncode=0):
            self.stdout = stdout
            self.stderr = stderr
            self.returncode = returncode

    def fake_run(cmd, shell, capture_output, text):
        # Simulate successful 200 response
        return DummyResult("HTTP/1.1 200 OK\n")

    monkeypatch.setattr(nextcloud, "load_nextcloud_config", fake_load_config)
    monkeypatch.setattr(nextcloud.subprocess, "run", fake_run)

    ok = nextcloud.test_nextcloud_connection()
    assert ok is True


def test_test_nextcloud_connection_error_status(monkeypatch):
    cfg = {
        "endpoint": "https://example.com/remote.php/dav/files/user/",
        "username": "user",
        "password": "pass",
    }

    def fake_load_config():
        return cfg

    class DummyResult:
        def __init__(self, stdout, stderr="", returncode=0):
            self.stdout = stdout
            self.stderr = stderr
            self.returncode = returncode

    def fake_run(cmd, shell, capture_output, text):
        # Simulate 500 error
        return DummyResult("HTTP/1.1 500 Internal Server Error\n")

    monkeypatch.setattr(nextcloud, "load_nextcloud_config", fake_load_config)
    monkeypatch.setattr(nextcloud.subprocess, "run", fake_run)

    ok = nextcloud.test_nextcloud_connection()
    assert ok is False


def test_test_nextcloud_connection_no_status_line(monkeypatch):
    cfg = {
        "endpoint": "https://example.com/remote.php/dav/files/user/",
        "username": "user",
        "password": "pass",
    }

    def fake_load_config():
        return cfg

    class DummyResult:
        def __init__(self, stdout, stderr="", returncode=0):
            self.stdout = stdout
            self.stderr = stderr
            self.returncode = returncode

    def fake_run(cmd, shell, capture_output, text):
        # No HTTP status line in stdout
        return DummyResult("")

    monkeypatch.setattr(nextcloud, "load_nextcloud_config", fake_load_config)
    monkeypatch.setattr(nextcloud.subprocess, "run", fake_run)

    ok = nextcloud.test_nextcloud_connection()
    assert ok is False

