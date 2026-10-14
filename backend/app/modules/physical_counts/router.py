from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.physical_counts import service
from app.modules.physical_counts.models import PhysicalCount
from app.modules.physical_counts.schemas import (
    PhysicalCountCreate,
    PhysicalCountLinesUpdate,
    PhysicalCountListItem,
    PhysicalCountResponse,
    PhysicalCountWarehouseOption,
)

router = APIRouter(prefix="/api/v1/inventory/physical-counts", tags=["physical-counts"])


@router.get("/options", response_model=list[PhysicalCountWarehouseOption])
def get_count_options(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory.physical_counts.read")),
) -> list[PhysicalCountWarehouseOption]:
    return service.get_count_options(db)


@router.get("", response_model=list[PhysicalCountListItem])
def list_counts(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory.physical_counts.read")),
) -> list[PhysicalCountListItem]:
    return service.list_counts(db, offset=offset, limit=limit)


@router.post("", response_model=PhysicalCountResponse, status_code=status.HTTP_201_CREATED)
def start_count(
    payload: PhysicalCountCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("inventory.physical_counts.create")),
) -> PhysicalCount:
    ip = request.client.host if request.client else None
    return service.start_count(db, payload, actor, ip)


@router.get("/{count_id}", response_model=PhysicalCountResponse)
def get_count(
    count_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory.physical_counts.read")),
) -> PhysicalCount:
    physical_count = service.get_count(db, count_id)
    if physical_count is None:
        raise HTTPException(status_code=404, detail="Physical count not found")
    return physical_count


@router.put("/{count_id}/lines", response_model=PhysicalCountResponse)
def update_counted_quantities(
    count_id: int,
    payload: PhysicalCountLinesUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("inventory.physical_counts.create")),
) -> PhysicalCount:
    ip = request.client.host if request.client else None
    return service.update_counted_quantities(db, count_id, payload, actor, ip)


@router.post("/{count_id}/post", response_model=PhysicalCountResponse)
def post_count(
    count_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("inventory.physical_counts.create")),
) -> PhysicalCount:
    ip = request.client.host if request.client else None
    return service.post_count(db, count_id, actor, ip)
