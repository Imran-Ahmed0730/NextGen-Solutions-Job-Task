from pathlib import Path

from app.core.config import get_settings

_configured_media_root = Path(get_settings().media_root)
MEDIA_ROOT = (
    _configured_media_root
    if _configured_media_root.is_absolute()
    else Path(__file__).resolve().parents[3] / _configured_media_root
)
COMPANY_MEDIA_ROOT = MEDIA_ROOT / "company"
DEFAULT_BRAND_ASSETS = {
    "logo": "/brand/company-logo.svg",
    "favicon": "/brand/favicon.svg",
}
ASSET_SETTINGS_KEYS = {
    "logo": "company_logo_path",
    "favicon": "company_favicon_path",
}
MAX_ASSET_SIZES = {"logo": 2 * 1024 * 1024, "favicon": 512 * 1024}
ASSET_MIME_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/x-icon": ".ico",
    "image/vnd.microsoft.icon": ".ico",
}


def get_asset_extension(asset_type: str, content_type: str, data: bytes) -> str | None:
    extension = ASSET_MIME_EXTENSIONS.get(content_type)
    if extension is None:
        return None
    if asset_type == "logo" and extension == ".ico":
        return None
    signatures = {
        ".png": data.startswith(b"\x89PNG\r\n\x1a\n"),
        ".jpg": data.startswith(b"\xff\xd8\xff"),
        ".webp": len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP",
        ".ico": data.startswith(b"\x00\x00\x01\x00"),
    }
    return extension if signatures[extension] else None
