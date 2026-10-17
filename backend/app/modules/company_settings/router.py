import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.company_settings import service
from app.modules.company_settings.models import CompanySetting
from app.modules.company_settings.schemas import (
    CompanyBrandingResponse,
    CompanySettingCreate,
    CompanySettingResponse,
    CompanySettingUpdate,
)
from app.modules.company_settings.storage import (
    ASSET_MIME_EXTENSIONS,
    ASSET_SETTINGS_KEYS,
    COMPANY_MEDIA_ROOT,
    MAX_ASSET_SIZES,
    get_asset_extension,
)

router = APIRouter(prefix="/api/v1/company-settings", tags=["company-settings"])


@router.get("", response_model=list[CompanySettingResponse])
def list_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master_data.company_settings.read")),
) -> list[CompanySetting]:
    return service.list_settings(db)


@router.get("/branding", response_model=CompanyBrandingResponse)
def get_branding(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("auth.profile.read")),
) -> dict[str, str]:
    return service.get_branding(db)


@router.put("/assets/{asset_type}", response_model=CompanySettingResponse)
async def upload_brand_asset(
    asset_type: Literal["logo", "favicon"],
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.company_settings.update")),
) -> CompanySetting:
    content_type = request.headers.get("content-type", "").split(";", maxsplit=1)[0].strip()
    if content_type not in ASSET_MIME_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported image type")

    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_ASSET_SIZES[asset_type]:
            raise HTTPException(
                status_code=413,
                detail=f"{asset_type.title()} file exceeds the size limit",
            )
        chunks.append(chunk)
    data = b"".join(chunks)
    extension = get_asset_extension(asset_type, content_type, data)
    if extension is None:
        raise HTTPException(status_code=415, detail="Image content does not match its file type")

    COMPANY_MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    filename = f"{asset_type}-{uuid.uuid4().hex}{extension}"
    destination = COMPANY_MEDIA_ROOT / filename
    destination.write_bytes(data)
    setting_value = f"/media/company/{filename}"
    try:
        setting = service.save_setting(
            db, ASSET_SETTINGS_KEYS[asset_type], setting_value, actor, _ip(request)
        )
    except (HTTPException, SQLAlchemyError):
        destination.unlink(missing_ok=True)
        raise
    return setting


@router.get("/{key}", response_model=CompanySettingResponse)
def get_setting(
    key: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master_data.company_settings.read")),
) -> CompanySetting:
    setting = service.get_setting(db, key)
    if setting is None:
        raise HTTPException(status_code=404, detail="Company setting not found")
    return setting


@router.post("", response_model=CompanySettingResponse, status_code=status.HTTP_201_CREATED)
def create_setting(
    payload: CompanySettingCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.company_settings.create")),
) -> CompanySetting:
    return service.create_setting_from_payload(db, payload.model_dump(), actor, _ip(request))


@router.put("/{key}", response_model=CompanySettingResponse)
@router.patch("/{key}", response_model=CompanySettingResponse)
def update_setting(
    key: str,
    payload: CompanySettingUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.company_settings.update")),
) -> CompanySetting:
    # Combine path key with payload value; allow payload to override key if provided.
    combined: dict[str, object] = {"key": key, "value": payload.value}
    return service.save_setting_from_payload(db, combined, actor, _ip(request))


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_setting(
    key: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.company_settings.delete")),
) -> None:
    service.delete_setting(db, key, actor, _ip(request))


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None
