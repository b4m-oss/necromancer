import json
import sys
from pathlib import Path

try:
    from .nextcloud import (
        upload_directory_to_nextcloud,
        upload_pdf_to_nextcloud,
        upload_file_to_nextcloud,
    )
except ImportError:
    _app_root = Path(__file__).resolve().parent.parent
    if str(_app_root) not in sys.path:
        sys.path.insert(0, str(_app_root))
    from lib.nextcloud import (
        upload_directory_to_nextcloud,
        upload_pdf_to_nextcloud,
        upload_file_to_nextcloud,
    )


class NextcloudUploader:
    """
    Upload adapter for Nextcloud.
    Wraps existing functions in nextcloud.py and exposes a simple interface.
    """

    def upload_directory(self, dir_path: str) -> bool:
        return upload_directory_to_nextcloud(dir_path)

    def upload_file(self, file_path: str) -> bool:
        return upload_file_to_nextcloud(file_path)

    def upload_pdf(self, pdf_path: str) -> bool:
        return upload_pdf_to_nextcloud(pdf_path)


def _load_upload_config_raw(config_path: str = str(Path(__file__).resolve().parent.parent / "config" / "upload.json")):
    """
    Helper to load raw data from upload.json.
    {
      "provider": "nextcloud",
      "nextcloud": { ... }
    }
    """
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_uploader_from_config():
    """
    Return an appropriate upload adapter based on upload.json.
    Currently only provider='nextcloud' is supported.
    """
    raw = _load_upload_config_raw()
    provider = raw.get("provider", "nextcloud")

    if provider == "nextcloud":
        return NextcloudUploader()

    # Future extension point: dropbox / gdrive etc.
    print(f"Warning: unsupported provider specified: {provider}. Falling back to Nextcloud.")
    return NextcloudUploader()


