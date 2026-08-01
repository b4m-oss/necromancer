import json
import os
from pathlib import Path

import pytest

from app.lib import scan


def test_load_scan_configs_success(tmp_path, monkeypatch):
    cfg_path = tmp_path / "mode.json"
    data = {"modes": {"dummy": {}}}
    cfg_path.write_text(json.dumps(data), encoding="utf-8")

    result = scan.load_scan_configs(str(cfg_path))
    assert result == data


def test_load_scan_configs_file_not_found(tmp_path):
    missing_path = tmp_path / "no_such_mode.json"
    with pytest.raises(FileNotFoundError):
        scan.load_scan_configs(str(missing_path))


def test_load_scanner_config_defaults_when_missing(tmp_path):
    missing = tmp_path / "scanner.json"
    result = scan.load_scanner_config(str(missing))
    assert result["device_name"] == "fujitsu:ScanSnap iX500:17872"
    assert result["vendor_keyword"] == "fujitsu"
    assert result["model_keyword"] == "ix500"
    assert result["backend"] == "fujitsu"
    assert result["default_source"] == "ADF Duplex"
    assert result["test_timeout_sec"] == 10


def test_load_scanner_config_merge_with_defaults(tmp_path):
    cfg_path = tmp_path / "scanner.json"
    custom = {
        "device_name": "custom_device",
        "vendor_keyword": "custom_vendor",
        "test_timeout_sec": 5,
    }
    cfg_path.write_text(json.dumps(custom), encoding="utf-8")

    result = scan.load_scanner_config(str(cfg_path))
    # Overridden
    assert result["device_name"] == "custom_device"
    assert result["vendor_keyword"] == "custom_vendor"
    assert result["test_timeout_sec"] == 5
    # Defaulted
    assert result["model_keyword"] == "ix500"
    assert result["backend"] == "fujitsu"
    assert result["default_source"] == "ADF Duplex"


def test_get_scanner_list_success(monkeypatch):
    class DummyResult:
        def __init__(self):
            self.stdout = "device `fujitsu:ScanSnap iX500:1234' is a scanner"

    def fake_run(cmd, capture_output, text, check):
        assert cmd == ["scanimage", "-L"]
        return DummyResult()

    monkeypatch.setattr(scan.subprocess, "run", fake_run)

    out = scan.get_scanner_list()
    assert "ScanSnap iX500" in out


def test_get_scanner_list_error(monkeypatch, capsys):
    class DummyError(Exception):
        pass

    def fake_run(cmd, capture_output, text, check):
        raise scan.subprocess.CalledProcessError(1, cmd, "err")

    monkeypatch.setattr(scan.subprocess, "run", fake_run)

    out = scan.get_scanner_list()
    captured = capsys.readouterr()
    assert out == ""
    assert "Error while listing scanners" in captured.out


def test_scanimage_scan_success(monkeypatch, tmp_path, capsys):
    output = tmp_path / "out.jpg"

    class DummyResult:
        def __init__(self):
            self.returncode = 0
            self.stderr = ""

    def fake_run(cmd, capture_output, text):
        # Basic shape of command should be as documented
        assert cmd[0] == "scanimage"
        assert any("--resolution=" in part for part in cmd)
        assert "-o" in cmd
        return DummyResult()

    monkeypatch.setattr(scan.subprocess, "run", fake_run)

    ok = scan.scanimage_scan(str(output), "devname")
    captured = capsys.readouterr()
    assert ok is True
    assert "Executing command:" in captured.out


def test_scanimage_scan_failure(monkeypatch):
    class DummyResult:
        def __init__(self):
            self.returncode = 1
            self.stderr = "some error"

    def fake_run(cmd, capture_output, text):
        return DummyResult()

    monkeypatch.setattr(scan.subprocess, "run", fake_run)

    ok = scan.scanimage_scan("/tmp/out.jpg", "devname")
    assert ok is False


def test_create_timestamp_dir(tmp_path, monkeypatch):
    # Monkeypatch base path so that tmp/ is under tmp_path
    base = tmp_path / "app" / "lib"
    base.mkdir(parents=True)

    def fake_resolve():
        return base / "scan.py"

    monkeypatch.setattr(scan.Path, "resolve", lambda self: fake_resolve())

    tmp_dir, ts = scan.create_timestamp_dir()
    assert tmp_dir.is_dir()
    assert ts.isdigit()
    assert len(ts) == 14  # YYYYMMDDHHMMSS


def test_convert_images_to_pdf_single(tmp_path):
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    img_path = img_dir / "page1.jpg"

    from PIL import Image

    Image.new("RGB", (100, 100), color="white").save(img_path)
    pdf_path = tmp_path / "out.pdf"

    ok = scan.convert_images_to_pdf(str(img_dir), str(pdf_path))
    assert ok is True
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0


def test_convert_images_to_pdf_multiple(tmp_path):
    img_dir = tmp_path / "images"
    img_dir.mkdir()

    from PIL import Image

    for i in range(3):
        Image.new("RGB", (100, 100), color="white").save(img_dir / f"page{i}.jpg")

    pdf_path = tmp_path / "out.pdf"
    ok = scan.convert_images_to_pdf(str(img_dir), str(pdf_path))
    assert ok is True
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0


def test_convert_images_to_pdf_no_images(tmp_path, capsys):
    img_dir = tmp_path / "empty"
    img_dir.mkdir()
    pdf_path = tmp_path / "out.pdf"

    ok = scan.convert_images_to_pdf(str(img_dir), str(pdf_path))
    captured = capsys.readouterr()
    assert ok is False
    assert "No image files found" in captured.out


def test_is_blank_page_true_and_false(tmp_path):
    from PIL import Image

    white = tmp_path / "white.jpg"
    black = tmp_path / "black.jpg"

    Image.new("L", (50, 50), color=255).save(white)
    Image.new("L", (50, 50), color=0).save(black)

    assert scan.is_blank_page(str(white)) is True
    assert scan.is_blank_page(str(black)) is False


def test_batch_scan_with_scanimage_config_missing(monkeypatch):
    monkeypatch.setattr(scan, "load_scan_configs", lambda: {})
    result = scan.batch_scan_with_scanimage("unknown", upload_to_nextcloud=False)
    assert result is None


def test_batch_scan_with_scanimage_basic(monkeypatch, tmp_path):
    # Minimal config: no PDF, no blank_filter, no upload
    configs = {
        "receipt": {
            "resolution": 300,
            "mode": "color",
            "source": "ADF Duplex",
            "file_format": "JPEG",
            "blank_filter": False,
        }
    }
    monkeypatch.setattr(scan, "load_scan_configs", lambda: configs)

    # tmp_dir はテスト用ディレクトリに固定
    def fake_create_timestamp_dir():
        return tmp_path, "20260101010101"

    monkeypatch.setattr(scan, "create_timestamp_dir", fake_create_timestamp_dir)
    monkeypatch.setattr(
        scan,
        "load_scanner_config",
        lambda: {
            "device_name": "dev",
            "backend": "fujitsu",
            "default_source": "ADF Duplex",
            "test_timeout_sec": 10,
        },
    )

    class DummyScanner:
        def warm_up_scanner(self):
            return True

    monkeypatch.setattr(
        scan.ScannerManager,
        "get_instance",
        classmethod(lambda cls: DummyScanner()),
    )

    class DummyResult:
        def __init__(self):
            self.stdout = ""
            self.stderr = "1 pages scanned"
            self.returncode = 0

    def fake_run(cmd, shell, capture_output, text, timeout):
        return DummyResult()

    monkeypatch.setattr(scan.subprocess, "run", fake_run)

    # ディレクトリ内容とファイルサイズ
    monkeypatch.setattr(scan.os, "listdir", lambda path: ["receipt-1.jpg"])
    monkeypatch.setattr(scan.os.path, "getsize", lambda p: 1024)

    # is_blank_page は呼ばれないよう blank_filter=False にしている
    result = scan.batch_scan_with_scanimage("receipt", upload_to_nextcloud=False)
    assert result == tmp_path


def test_batch_scan_with_scanimage_blank_filter_and_pdf_upload(monkeypatch, tmp_path):
    # Config with blank_filter and PDF
    configs = {
        "diary": {
            "resolution": 300,
            "mode": "color",
            "source": "ADF Duplex",
            "file_format": "PDF",
            "blank_filter": True,
        }
    }
    monkeypatch.setattr(scan, "load_scan_configs", lambda: configs)

    # tmp_dir fixed
    def fake_create_timestamp_dir():
        tdir = tmp_path / "scan"
        tdir.mkdir(exist_ok=True)
        return tdir, "20260101010101"

    monkeypatch.setattr(scan, "create_timestamp_dir", fake_create_timestamp_dir)
    monkeypatch.setattr(
        scan,
        "load_scanner_config",
        lambda: {
            "device_name": "dev",
            "backend": "fujitsu",
            "default_source": "ADF Duplex",
            "test_timeout_sec": 10,
        },
    )

    class DummyScanner:
        def warm_up_scanner(self):
            return True

    monkeypatch.setattr(
        scan.ScannerManager,
        "get_instance",
        classmethod(lambda cls: DummyScanner()),
    )

    class DummyResult:
        def __init__(self):
            self.stdout = ""
            self.stderr = "2 pages scanned"
            self.returncode = 0

    def fake_run(cmd, shell, capture_output, text, timeout):
        return DummyResult()

    monkeypatch.setattr(scan.subprocess, "run", fake_run)

    # Simulate two JPEGs, one blank and one not
    img_dir = tmp_path / "scan"
    img_dir.mkdir(exist_ok=True)
    files = ["diary-1.jpg", "diary-2.jpg"]

    def fake_listdir(path):
        return files

    monkeypatch.setattr(scan.os, "listdir", fake_listdir)

    def fake_getsize(path):
        return 1024

    monkeypatch.setattr(scan.os.path, "getsize", lambda p: fake_getsize(p))

    # is_blank_page: first true (removed), second false (kept)
    def fake_is_blank(path):
        return "diary-1" in path

    monkeypatch.setattr(scan, "is_blank_page", fake_is_blank)

    # convert_images_to_pdf succeeds
    def fake_convert(image_dir, output_pdf):
        Path(output_pdf).parent.mkdir(parents=True, exist_ok=True)
        Path(output_pdf).write_bytes(b"%PDF-1.4 dummy")
        return True

    monkeypatch.setattr(scan, "convert_images_to_pdf", fake_convert)

    # Fake uploader
    class DummyUploader:
        def __init__(self):
            self.called_pdf = []

        def upload_pdf(self, pdf_path):
            self.called_pdf.append(pdf_path)
            return True

        def upload_directory(self, dir_path):
            return True

    dummy_uploader = DummyUploader()
    monkeypatch.setattr(scan, "get_uploader_from_config", lambda: dummy_uploader)

    result = scan.batch_scan_with_scanimage("diary", upload_to_nextcloud=True)
    # tmp_dir が返ってくる（PDF アップロード後でも tmp は削除されうるが、ここでは存在確認より戻り値優先）
    assert result == img_dir
    assert len(dummy_uploader.called_pdf) == 1


def test_single_scan_with_scanimage_config_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(scan, "load_scan_configs", lambda: {})
    ok = scan.single_scan_with_scanimage(str(tmp_path / "out.jpg"), "unknown", upload_to_nextcloud=False)
    assert ok is False


def test_single_scan_with_scanimage_success(monkeypatch, tmp_path):
    cfgs = {
        "receipt": {
            "resolution": 200,
            "mode": "color",
            "source": "ADF Duplex",
        }
    }
    monkeypatch.setattr(scan, "load_scan_configs", lambda: cfgs)
    monkeypatch.setattr(
        scan,
        "load_scanner_config",
        lambda: {
            "device_name": "dev",
            "backend": "fujitsu",
            "default_source": "ADF Duplex",
            "test_timeout_sec": 10,
        },
    )

    class DummyScanner:
        def warm_up_scanner(self):
            return True

    monkeypatch.setattr(
        scan.ScannerManager,
        "get_instance",
        classmethod(lambda cls: DummyScanner()),
    )

    class DummyResult:
        def __init__(self):
            self.stdout = ""
            self.stderr = ""
            self.returncode = 0

    def fake_run(cmd, shell, capture_output, text, timeout):
        return DummyResult()

    monkeypatch.setattr(scan.subprocess, "run", fake_run)

    out = tmp_path / "out.jpg"
    ok = scan.single_scan_with_scanimage(str(out), "receipt", upload_to_nextcloud=False)
    assert ok is True


def test_single_scan_with_scanimage_upload(monkeypatch, tmp_path):
    cfgs = {
        "receipt": {
            "resolution": 200,
            "mode": "color",
            "source": "ADF Duplex",
        }
    }
    monkeypatch.setattr(scan, "load_scan_configs", lambda: cfgs)
    monkeypatch.setattr(
        scan,
        "load_scanner_config",
        lambda: {
            "device_name": "dev",
            "backend": "fujitsu",
            "default_source": "ADF Duplex",
            "test_timeout_sec": 10,
        },
    )

    class DummyScanner:
        def warm_up_scanner(self):
            return True

    monkeypatch.setattr(
        scan.ScannerManager,
        "get_instance",
        classmethod(lambda cls: DummyScanner()),
    )

    class DummyResult:
        def __init__(self):
            self.stdout = ""
            self.stderr = ""
            self.returncode = 0

    def fake_run(cmd, shell, capture_output, text, timeout):
        return DummyResult()

    monkeypatch.setattr(scan.subprocess, "run", fake_run)

    called = {}

    class DummyUploader:
        def upload_file(self, path):
            called["path"] = path
            return True

    monkeypatch.setattr(scan, "get_uploader_from_config", lambda: DummyUploader())

    out = tmp_path / "out.jpg"
    ok = scan.single_scan_with_scanimage(str(out), "receipt", upload_to_nextcloud=True)
    assert ok is True
    assert called["path"] == str(out)


def test_single_scan_with_scanimage_warmup_fail(monkeypatch, tmp_path):
    cfgs = {"receipt": {"resolution": 200, "mode": "color"}}
    monkeypatch.setattr(scan, "load_scan_configs", lambda: cfgs)
    monkeypatch.setattr(scan, "load_scanner_config", lambda: {"device_name": "dev"})

    class DummyScanner:
        def warm_up_scanner(self):
            return False

    monkeypatch.setattr(
        scan.ScannerManager,
        "get_instance",
        classmethod(lambda cls: DummyScanner()),
    )

    ok = scan.single_scan_with_scanimage(str(tmp_path / "out.jpg"), "receipt", upload_to_nextcloud=False)
    assert ok is False


def test_scanner_manager_check_available_found(monkeypatch):
    mgr = scan.ScannerManager()

    class DummyResult:
        def __init__(self):
            self.stdout = f"device `{mgr.device_name}' is a scanner"
            self.stderr = ""
            self.returncode = 0

    def fake_run(cmd, shell, capture_output, text, timeout):
        return DummyResult()

    monkeypatch.setattr(scan.subprocess, "run", fake_run)

    assert mgr.check_scanner_available() is True


def test_scanner_manager_check_available_update_name(monkeypatch):
    mgr = scan.ScannerManager()
    mgr.device_name = "old-name"

    class DummyResult:
        def __init__(self):
            self.stdout = "device `fujitsu:ScanSnap iX500:9999' is a scanner"
            self.stderr = ""
            self.returncode = 0

    def fake_run(cmd, shell, capture_output, text, timeout):
        return DummyResult()

    monkeypatch.setattr(scan.subprocess, "run", fake_run)

    ok = mgr.check_scanner_available()
    assert ok is True
    assert "ScanSnap iX500" in mgr.device_name


def test_scanner_manager_check_available_exception(monkeypatch):
    mgr = scan.ScannerManager()

    def fake_run(cmd, shell, capture_output, text, timeout):
        raise RuntimeError("boom")

    monkeypatch.setattr(scan.subprocess, "run", fake_run)
    assert mgr.check_scanner_available() is True


def test_scanner_manager_warm_up_scanner(monkeypatch):
    mgr = scan.ScannerManager()

    # check_scanner_available -> True
    monkeypatch.setattr(mgr, "check_scanner_available", lambda: True)

    class DummyResult:
        def __init__(self):
            self.stdout = ""
            self.stderr = ""
            self.returncode = 0

    def fake_run(cmd, shell, capture_output, text, timeout):
        return DummyResult()

    monkeypatch.setattr(scan.subprocess, "run", fake_run)

    assert mgr.warm_up_scanner() is True


def test_single_scan_with_scanimage_timeout_file_exists(monkeypatch, tmp_path):
    cfgs = {"receipt": {"resolution": 200, "mode": "color"}}
    monkeypatch.setattr(scan, "load_scan_configs", lambda: cfgs)
    monkeypatch.setattr(scan, "load_scanner_config", lambda: {"device_name": "dev"})

    class DummyScanner:
        def warm_up_scanner(self):
            return True

    monkeypatch.setattr(
        scan.ScannerManager,
        "get_instance",
        classmethod(lambda cls: DummyScanner()),
    )

    def fake_run(cmd, shell, capture_output, text, timeout):
        raise scan.subprocess.TimeoutExpired(cmd, timeout)

    monkeypatch.setattr(scan.subprocess, "run", fake_run)

    out = tmp_path / "out.jpg"
    out.write_bytes(b"data")

    ok = scan.single_scan_with_scanimage(str(out), "receipt", upload_to_nextcloud=False)
    assert ok is True
    

def test_build_batch_scan_command_basic(monkeypatch):
    # Minimal mode/scanner configs
    monkeypatch.setattr(
        scan,
        "load_scan_configs",
        lambda: {
            "receipt": {
                "resolution": 200,
                "mode": "color",
                "source": "ADF Duplex",
                "file_format": "jpeg",
                "swdeskew": True,
                "swcrop": True,
                "ald": True,
                "max_page_height_mm": 600,
            }
        },
    )
    monkeypatch.setattr(
        scan,
        "load_scanner_config",
        lambda: {
            "device_name": "dev",
            "backend": "fujitsu",
            "default_source": "ADF Duplex",
            "test_timeout_sec": 10,
        },
    )

    info = scan.build_batch_scan_command("receipt")
    assert info["type"] == "batch"
    assert info["mode"] == "receipt"
    cmd = info["command"]
    assert "scanimage" in cmd
    assert "--resolution=200" in cmd
    assert "--mode=Color" in cmd
    # placeholder patterns are used for timestamp and filename
    assert "{timestamp}" in info["output_pattern"]
    assert "receipt-%d.jpg" in info["output_pattern"]


def test_build_batch_scan_command_mode_not_found(monkeypatch):
    monkeypatch.setattr(scan, "load_scan_configs", lambda: {})
    with pytest.raises(ValueError):
        scan.build_batch_scan_command("unknown")


def test_build_upload_target_info_nextcloud(monkeypatch):
    # Mode config (only file_format is relevant here)
    monkeypatch.setattr(
        scan,
        "load_scan_configs",
        lambda: {
            "diary": {
                "file_format": "PDF",
            }
        },
    )

    def fake_load_nc():
        return {
            "endpoint": "https://example.com/remote.php/dav/files/user/",
            "upload_folder": "Scans/",
            "delete_after_upload": True,
        }

    monkeypatch.setattr(scan, "load_nextcloud_config", fake_load_nc)

    info = scan.build_upload_target_info("diary")
    assert info["provider"] == "nextcloud"
    assert info["endpoint"].startswith("https://example.com")
    assert info["upload_folder"] == "Scans/"
    assert info["strategy"] == "pdf"
    assert "Scans/diary-" in info["remote_path_pattern"]
    assert "{timestamp}.pdf" in info["remote_path_pattern"]


def test_dump_config_text_contains_sections(monkeypatch):
    def fake_build_batch(mode):
        return {
            "type": "batch",
            "mode": mode,
            "command": 'scanimage --device="dev" --resolution=200 --mode=Color',
            "output_pattern": "/tmp/{timestamp}/receipt-%d.jpg",
            "effective_params": {
                "device_name": "dev",
                "resolution": 200,
                "mode": "Color",
            },
        }

    def fake_build_upload(mode):
        return {
            "provider": "nextcloud",
            "mode": mode,
            "endpoint": "https://example.com/remote.php/dav/files/user/",
            "upload_folder": "Scans/",
            "delete_after_upload": False,
            "strategy": "directory",
            "remote_path_pattern": "Scans/{timestamp}/",
        }

    monkeypatch.setattr(scan, "build_batch_scan_command", fake_build_batch)
    monkeypatch.setattr(scan, "build_upload_target_info", fake_build_upload)

    text = scan.dump_config("receipt")
    assert "=== scanimage command (batch) ===" in text
    assert "=== upload target ===" in text
    assert "scanimage --device=\"dev\"" in text
    assert "endpoint" in text
    assert "upload_folder" in text


def test_cli_dump_config_success(monkeypatch, capsys):
    def fake_dump(mode):
        assert mode == "receipt"
        return "DUMP-OK"

    monkeypatch.setattr(scan, "dump_config", fake_dump)

    exit_code = scan.main(["--dump-config", "receipt"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "DUMP-OK" in captured.out


def test_cli_dump_config_invalid_mode(monkeypatch, capsys):
    def fake_dump(mode):
        raise ValueError(f"configuration '{mode}' is not defined in mode.json")

    monkeypatch.setattr(scan, "dump_config", fake_dump)

    exit_code = scan.main(["--dump-config", "unknown"])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "configuration 'unknown' is not defined in mode.json" in captured.err


def test_cli_dump_config_conflict_with_other_options(monkeypatch, capsys):
    # dump_config 自体は呼ばれない想定
    called = {}

    def fake_dump(mode):
        called["mode"] = mode
        return "SHOULD NOT BE CALLED"

    monkeypatch.setattr(scan, "dump_config", fake_dump)

    exit_code = scan.main(["--dump-config", "receipt", "receipt"])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "cannot be combined" in captured.err
    assert called == {}


def test_cli_dry_run_check_success(monkeypatch):
    called = {}

    def fake_check():
        called["check"] = True
        return True

    monkeypatch.setattr(scan, "run_dry_run_check", fake_check)

    exit_code = scan.main(["--dry-run", "check"])
    assert exit_code == 0
    assert called.get("check") is True


def test_cli_dry_run_check_with_config_error(monkeypatch, capsys):
    exit_code = scan.main(["--dry-run", "check", "receipt"])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "must not be combined" in captured.err


def test_cli_dry_run_scan_requires_config(monkeypatch, capsys):
    exit_code = scan.main(["--dry-run", "scan"])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "requires a config name" in captured.err


def test_cli_dry_run_scan_success(monkeypatch):
    called = {}

    def fake_single(mode):
        called["mode"] = mode
        return True

    monkeypatch.setattr(scan, "run_dry_run_single_scan", fake_single)

    exit_code = scan.main(["--dry-run", "scan", "receipt"])
    assert exit_code == 0
    assert called.get("mode") == "receipt"


def test_cli_dry_run_conflicts_with_other_options(monkeypatch, capsys):
    exit_code = scan.main(["--dry-run", "check", "--dump-config", "receipt"])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "--dry-run cannot be combined" in captured.err


def test_run_health_check_all_ok(monkeypatch, capsys, tmp_path):
    # Scanners list
    monkeypatch.setattr(
        scan,
        "get_scanner_list",
        lambda: "device `dev' is a scanner\n",
    )

    # Configured scanner via ScannerManager
    class DummyScanner:
        def __init__(self):
            self.device_name = "dev"

        def check_scanner_available(self):
            return True

        def warm_up_scanner(self):
            return True

    monkeypatch.setattr(
        scan.ScannerManager,
        "get_instance",
        classmethod(lambda cls: DummyScanner()),
    )

    # Cloud config (Nextcloud, reachable)
    def fake_load_upload():
        return {
            "provider": "nextcloud",
            "nextcloud": {
                "endpoint": "https://example.com/remote.php/dav/files/user/",
            },
        }

    monkeypatch.setattr(scan, "_load_upload_config_raw", fake_load_upload)

    def fake_load_nc():
        return {
            "endpoint": "https://example.com/remote.php/dav/files/user/",
            "upload_folder": "Scans/",
        }

    monkeypatch.setattr(scan, "load_nextcloud_config", lambda: fake_load_nc())

    import app.lib.nextcloud as nc_mod

    monkeypatch.setattr(nc_mod, "test_nextcloud_connection", lambda: True)

    # Daemon running
    monkeypatch.setattr(
        scan,
        "check_keypad_daemon_running",
        lambda: (True, ["user      1234  0.0  keypad_daemon.py"]),
    )

    ok = scan.run_health_check()
    captured = capsys.readouterr()
    assert ok is True
    assert "=== Health Check ===" in captured.out
    assert "[Scanners]" in captured.out
    assert "[Configured scanner]" in captured.out
    assert "[Cloud]" in captured.out
    assert "[Daemon]" in captured.out
    assert "running: true" in captured.out


def test_run_health_check_cloud_ng(monkeypatch, capsys):
    monkeypatch.setattr(
        scan,
        "get_scanner_list",
        lambda: "device `dev' is a scanner\n",
    )

    class DummyScanner:
        def __init__(self):
            self.device_name = "dev"

        def check_scanner_available(self):
            return True

        def warm_up_scanner(self):
            return True

    monkeypatch.setattr(
        scan.ScannerManager,
        "get_instance",
        classmethod(lambda cls: DummyScanner()),
    )

    def fake_load_upload():
        return {
            "provider": "nextcloud",
            "nextcloud": {
                "endpoint": "https://example.com/remote.php/dav/files/user/",
            },
        }

    monkeypatch.setattr(scan, "_load_upload_config_raw", fake_load_upload)

    def fake_load_nc():
        return {
            "endpoint": "https://example.com/remote.php/dav/files/user/",
            "upload_folder": "Scans/",
        }

    monkeypatch.setattr(scan, "load_nextcloud_config", lambda: fake_load_nc())

    import app.lib.nextcloud as nc_mod

    monkeypatch.setattr(nc_mod, "test_nextcloud_connection", lambda: False)

    monkeypatch.setattr(
        scan,
        "check_keypad_daemon_running",
        lambda: (True, []),
    )

    ok = scan.run_health_check()
    captured = capsys.readouterr()
    assert ok is False
    assert "reachable: false" in captured.out


def test_run_health_check_provider_not_nextcloud(monkeypatch, capsys):
    monkeypatch.setattr(
        scan,
        "get_scanner_list",
        lambda: "device `dev' is a scanner\n",
    )

    class DummyScanner:
        def __init__(self):
            self.device_name = "dev"

        def check_scanner_available(self):
            return True

        def warm_up_scanner(self):
            return True

    monkeypatch.setattr(
        scan.ScannerManager,
        "get_instance",
        classmethod(lambda cls: DummyScanner()),
    )

    def fake_load_upload():
        return {
            "provider": "local",
            "local": {"endpoint": "/some/path"},
        }

    monkeypatch.setattr(scan, "_load_upload_config_raw", fake_load_upload)

    monkeypatch.setattr(
        scan,
        "check_keypad_daemon_running",
        lambda: (True, []),
    )

    ok = scan.run_health_check()
    captured = capsys.readouterr()
    assert ok is True
    assert "provider: local" in captured.out
    assert "reachable: N/A" in captured.out


def test_run_health_check_scanners_fail(monkeypatch, capsys):
    def fake_get_scanners():
        raise RuntimeError("boom")

    monkeypatch.setattr(scan, "get_scanner_list", fake_get_scanners)

    class DummyScanner:
        def __init__(self):
            self.device_name = "dev"

        def check_scanner_available(self):
            return True

        def warm_up_scanner(self):
            return True

    monkeypatch.setattr(
        scan.ScannerManager,
        "get_instance",
        classmethod(lambda cls: DummyScanner()),
    )

    def fake_load_upload():
        return {
            "provider": "nextcloud",
            "nextcloud": {
                "endpoint": "https://example.com/remote.php/dav/files/user/",
            },
        }

    monkeypatch.setattr(scan, "_load_upload_config_raw", fake_load_upload)

    def fake_load_nc():
        return {
            "endpoint": "https://example.com/remote.php/dav/files/user/",
            "upload_folder": "Scans/",
        }

    monkeypatch.setattr(scan, "load_nextcloud_config", lambda: fake_load_nc())

    import app.lib.nextcloud as nc_mod

    monkeypatch.setattr(nc_mod, "test_nextcloud_connection", lambda: True)

    monkeypatch.setattr(
        scan,
        "check_keypad_daemon_running",
        lambda: (True, []),
    )

    ok = scan.run_health_check()
    captured = capsys.readouterr()
    assert ok is False
    assert "Scanners: NG" in captured.out


def test_cli_health_success(monkeypatch, capsys):
    called = {}

    def fake_health():
        called["run"] = True
        print("=== Health Check ===")
        return True

    monkeypatch.setattr(scan, "run_health_check", fake_health)

    exit_code = scan.main(["--health"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert called.get("run") is True
    assert "Health Check" in captured.out


def test_cli_health_failure(monkeypatch):
    def fake_health():
        return False

    monkeypatch.setattr(scan, "run_health_check", fake_health)

    exit_code = scan.main(["--health"])
    assert exit_code == 1


def test_cli_health_conflict_with_other_options(monkeypatch, capsys):
    def fake_health():
        raise AssertionError("should not be called")

    monkeypatch.setattr(scan, "run_health_check", fake_health)

    exit_code = scan.main(["--health", "--dump-config", "receipt"])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "--health cannot be combined" in captured.err

