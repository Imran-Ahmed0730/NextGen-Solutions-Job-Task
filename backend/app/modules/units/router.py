from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.units import service
from app.modules.units.models import Unit
from app.modules.units.repository import get_unit
from app.modules.units.schemas import UnitCreate, UnitResponse, UnitUpdate

router = APIRouter(prefix="/api/v1/units", tags=["units"])


def _unit_or_404(db: Session, unit_id: int) -> Unit:
    unit = get_unit(db, unit_id)
    if unit is None:
        raise HTTPException(status_code=404, detail="Unit not found")
    return unit


@router.get("", response_model=list[UnitResponse])
def list_units(
    include_inactive: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master_data.units.read")),
) -> list[Unit]:
    return service.list_units(db, include_inactive=include_inactive, offset=offset, limit=limit)


@router.post("", response_model=UnitResponse, status_code=status.HTTP_201_CREATED)
def create_unit(
    payload: UnitCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.units.create")),
) -> Unit:
    return service.create_unit(db, payload.model_dump(), actor, _ip(request))


@router.patch("/{unit_id}", response_model=UnitResponse)
def update_unit(
    unit_id: int,
    payload: UnitUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.units.update")),
) -> Unit:
    unit = _unit_or_404(db, unit_id)
    return service.update_unit(
        db, unit, payload.model_dump(exclude_unset=True), actor, _ip(request)
    )


@router.delete("/{unit_id}", response_model=UnitResponse)
def delete_unit(
    unit_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.units.delete")),
) -> Unit:
    return service.delete_unit(db, _unit_or_404(db, unit_id), actor, _ip(request))


@router.post("/{unit_id}/activate", response_model=UnitResponse)
def activate_unit(
    unit_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.units.update")),
) -> Unit:
    return service.activate_unit(db, _unit_or_404(db, unit_id), actor, _ip(request))


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None
