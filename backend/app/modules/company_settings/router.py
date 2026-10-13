from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.company_settings import service
from app.modules.company_settings.models import CompanySetting
from app.modules.company_settings.schemas import (
    CompanySettingCreate,
    CompanySettingResponse,
    CompanySettingUpdate,
)

router = APIRouter(prefix="/api/v1/company-settings", tags=["company-settings"])


@router.get("", response_model=list[CompanySettingResponse])
def list_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master_data.company_settings.read")),
) -> list[CompanySetting]:
    return service.list_settings(db)


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
    return service.create_setting_from_payload(
        db, payload.model_dump(), actor, _ip(request)
    )


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