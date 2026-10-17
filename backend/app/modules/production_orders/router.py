from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.production_orders import service
from app.modules.production_orders.models import ProductionOrder
from app.modules.production_orders.schemas import (
    ProductionOrderComplete,
    ProductionOrderCreate,
    ProductionOrderOptionsResponse,
    ProductionOrderResponse,
)

router = APIRouter(prefix="/api/v1/production/orders", tags=["production-orders"])


@router.get("/options", response_model=ProductionOrderOptionsResponse)
def get_production_order_options(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("production.orders.read")),
) -> ProductionOrderOptionsResponse:
    return service.get_production_order_options(db)


@router.get("", response_model=list[ProductionOrderResponse])
def list_production_orders(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("production.orders.read")),
) -> list[ProductionOrder]:
    return service.list_production_orders(db, offset=offset, limit=limit)


@router.post("", response_model=ProductionOrderResponse, status_code=status.HTTP_201_CREATED)
def create_production_order(
    payload: ProductionOrderCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("production.orders.create")),
) -> ProductionOrder:
    return service.create_production_order(db, payload, actor, _ip(request))


@router.get("/{production_order_id}", response_model=ProductionOrderResponse)
def get_production_order(
    production_order_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("production.orders.read")),
) -> ProductionOrder:
    order = service.get_production_order(db, production_order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Production order not found")
    return order


@router.put("/{production_order_id}", response_model=ProductionOrderResponse)
def update_production_order(
    production_order_id: int,
    payload: ProductionOrderCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("production.orders.update")),
) -> ProductionOrder:
    return service.update_production_order(db, production_order_id, payload, actor, _ip(request))


@router.post("/{production_order_id}/start", response_model=ProductionOrderResponse)
def start_production_order(
    production_order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("production.orders.update")),
) -> ProductionOrder:
    return service.start_production_order(db, production_order_id, actor, _ip(request))


@router.post("/{production_order_id}/complete", response_model=ProductionOrderResponse)
def complete_production_order(
    production_order_id: int,
    payload: ProductionOrderComplete,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("production.orders.update")),
) -> ProductionOrder:
    return service.complete_production_order(db, production_order_id, payload, actor, _ip(request))


@router.post("/{production_order_id}/cancel", response_model=ProductionOrderResponse)
def cancel_production_order(
    production_order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("production.orders.update")),
) -> ProductionOrder:
    return service.cancel_production_order(db, production_order_id, actor, _ip(request))


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None
