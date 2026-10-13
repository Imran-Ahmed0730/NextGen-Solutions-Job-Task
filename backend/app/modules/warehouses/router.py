from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.warehouses import service
from app.modules.warehouses.models import Warehouse
from app.modules.warehouses.schemas import (
    WarehouseCreate,
    WarehouseResponse,
    WarehouseUpdate,
)

router = APIRouter(prefix="/api/v1/warehouses", tags=["warehouses"])


def _warehouse_or_404(db: Session, warehouse_id: int) -> Warehouse:
    warehouse = service.get_warehouse(db, warehouse_id)
    if warehouse is None:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return warehouse


@router.get("", response_model=list[WarehouseResponse])
def list_warehouses(
    include_inactive: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master_data.warehouses.read")),
) -> list[Warehouse]:
    return service.list_warehouses(
        db, include_inactive=include_inactive, offset=offset, limit=limit
    )


@router.post("", response_model=WarehouseResponse, status_code=status.HTTP_201_CREATED)
def create_warehouse(
    payload: WarehouseCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.warehouses.create")),
) -> Warehouse:
    return service.create_warehouse(db, payload.model_dump(), actor, _ip(request))


@router.get("/{warehouse_id}", response_model=WarehouseResponse)
def get_warehouse(
    warehouse_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master_data.warehouses.read")),
) -> Warehouse:
    return _warehouse_or_404(db, warehouse_id)


@router.patch("/{warehouse_id}", response_model=WarehouseResponse)
def update_warehouse(
    warehouse_id: int,
    payload: WarehouseUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.warehouses.update")),
) -> Warehouse:
    warehouse = _warehouse_or_404(db, warehouse_id)
    return service.update_warehouse(
        db, warehouse, payload.model_dump(exclude_unset=True), actor, _ip(request)
    )


@router.delete("/{warehouse_id}", response_model=WarehouseResponse)
def delete_warehouse(
    warehouse_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.warehouses.delete")),
) -> Warehouse:
    return service.delete_warehouse(db, _warehouse_or_404(db, warehouse_id), actor, _ip(request))


@router.post("/{warehouse_id}/activate", response_model=WarehouseResponse)
def activate_warehouse(
    warehouse_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.warehouses.update")),
) -> Warehouse:
    return service.activate_warehouse(
        db, _warehouse_or_404(db, warehouse_id), actor, _ip(request)
    )


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None
