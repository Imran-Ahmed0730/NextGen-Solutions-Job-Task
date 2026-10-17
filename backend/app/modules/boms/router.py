from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.boms import service
from app.modules.boms.models import BOM
from app.modules.boms.schemas import BOMCreate, BOMOptionsResponse, BOMResponse

router = APIRouter(prefix="/api/v1/production/boms", tags=["production-boms"])


@router.get("/options", response_model=BOMOptionsResponse)
def get_bom_options(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("production.boms.read")),
) -> BOMOptionsResponse:
    return service.get_bom_options(db)


@router.get("", response_model=list[BOMResponse])
def list_boms(
    include_inactive: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("production.boms.read")),
) -> list[BOM]:
    return service.list_boms(db, include_inactive=include_inactive, offset=offset, limit=limit)


@router.post("", response_model=BOMResponse, status_code=status.HTTP_201_CREATED)
def create_bom(
    payload: BOMCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("production.boms.create")),
) -> BOM:
    return service.create_bom(db, payload, actor, _ip(request))


@router.put("/{bom_id}", response_model=BOMResponse)
def update_bom(
    bom_id: int,
    payload: BOMCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("production.boms.update")),
) -> BOM:
    return service.update_bom(db, bom_id, payload, actor, _ip(request))


@router.delete("/{bom_id}", response_model=BOMResponse)
def delete_bom(
    bom_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("production.boms.delete")),
) -> BOM:
    return service.set_bom_active(db, bom_id, active=False, actor=actor, ip=_ip(request))


@router.post("/{bom_id}/activate", response_model=BOMResponse)
def activate_bom(
    bom_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("production.boms.update")),
) -> BOM:
    return service.set_bom_active(db, bom_id, active=True, actor=actor, ip=_ip(request))


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None
