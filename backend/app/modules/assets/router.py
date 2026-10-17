from datetime import date

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.assets import service
from app.modules.assets.models import Asset
from app.modules.assets.schemas import (
    AssetAssignmentCreate,
    AssetCreate,
    AssetMaintenanceCreate,
    AssetResponse,
    AssetUpdate,
)
from app.modules.auth.models import User

router = APIRouter(prefix="/api/v1/assets", tags=["assets"])


@router.get("", response_model=list[AssetResponse])
def list_assets(
    include_inactive: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("assets.read")),
) -> list[Asset]:
    return service.list_assets(db, include_inactive=include_inactive, offset=offset, limit=limit)


@router.post("", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
def create_asset(
    payload: AssetCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("assets.create")),
) -> Asset:
    return service.create_asset(db, payload.model_dump(), actor, _ip(request))


@router.patch("/{asset_id}", response_model=AssetResponse)
def update_asset(
    asset_id: int,
    payload: AssetUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("assets.update")),
) -> Asset:
    return service.update_asset(
        db, asset_id, payload.model_dump(exclude_unset=True), actor, _ip(request)
    )


@router.delete("/{asset_id}", response_model=AssetResponse)
def delete_asset(
    asset_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("assets.delete")),
) -> Asset:
    return service.delete_asset(db, asset_id, actor, _ip(request))


@router.post("/{asset_id}/restore", response_model=AssetResponse)
def restore_asset(
    asset_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("assets.update")),
) -> Asset:
    return service.restore_asset(db, asset_id, actor, _ip(request))


@router.post(
    "/{asset_id}/assignments",
    response_model=AssetResponse,
    status_code=status.HTTP_201_CREATED,
)
def assign_asset(
    asset_id: int,
    payload: AssetAssignmentCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("assets.assign")),
) -> Asset:
    return service.assign_asset(db, asset_id, payload.model_dump(), actor, _ip(request))


@router.post(
    "/{asset_id}/assignments/{assignment_id}/return",
    response_model=AssetResponse,
)
def return_asset(
    asset_id: int,
    assignment_id: int,
    request: Request,
    returned_on: date = Query(),
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("assets.assign")),
) -> Asset:
    return service.return_asset(db, asset_id, assignment_id, returned_on, actor, _ip(request))


@router.post(
    "/{asset_id}/maintenance",
    response_model=AssetResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_maintenance(
    asset_id: int,
    payload: AssetMaintenanceCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("assets.maintain")),
) -> Asset:
    return service.add_maintenance(db, asset_id, payload.model_dump(), actor, _ip(request))


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None
