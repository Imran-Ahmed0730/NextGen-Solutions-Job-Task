from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.purchase_orders import service
from app.modules.purchase_orders.models import PurchaseOrder
from app.modules.purchase_orders.schemas import (
    PurchaseOrderCreate,
    PurchaseOrderOptionsResponse,
    PurchaseOrderResponse,
    PurchaseOrderUpdate,
)

router = APIRouter(prefix="/api/v1/purchase/orders", tags=["purchase-orders"])


@router.get("/options", response_model=PurchaseOrderOptionsResponse)
def get_purchase_order_options(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("purchase.orders.read")),
) -> PurchaseOrderOptionsResponse:
    return service.get_purchase_order_options(db)


@router.get("", response_model=list[PurchaseOrderResponse])
def list_purchase_orders(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("purchase.orders.read")),
) -> list[PurchaseOrder]:
    return service.list_purchase_orders(db, offset=offset, limit=limit)


@router.post("", response_model=PurchaseOrderResponse, status_code=status.HTTP_201_CREATED)
def create_purchase_order(
    payload: PurchaseOrderCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("purchase.orders.create")),
) -> PurchaseOrder:
    ip = request.client.host if request.client else None
    return service.create_purchase_order(db, payload, actor, ip)


@router.get("/{purchase_order_id}", response_model=PurchaseOrderResponse)
def get_purchase_order(
    purchase_order_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("purchase.orders.read")),
) -> PurchaseOrder:
    purchase_order = service.get_purchase_order(db, purchase_order_id)
    if purchase_order is None:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return purchase_order


@router.put("/{purchase_order_id}", response_model=PurchaseOrderResponse)
def update_purchase_order(
    purchase_order_id: int,
    payload: PurchaseOrderUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("purchase.orders.update")),
) -> PurchaseOrder:
    ip = request.client.host if request.client else None
    return service.update_purchase_order(db, purchase_order_id, payload, actor, ip)


@router.post("/{purchase_order_id}/submit", response_model=PurchaseOrderResponse)
def submit_purchase_order(
    purchase_order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("purchase.orders.submit")),
) -> PurchaseOrder:
    ip = request.client.host if request.client else None
    return service.submit_purchase_order(db, purchase_order_id, actor, ip)


@router.post("/{purchase_order_id}/approve", response_model=PurchaseOrderResponse)
def approve_purchase_order(
    purchase_order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("purchase.orders.approve")),
) -> PurchaseOrder:
    ip = request.client.host if request.client else None
    return service.approve_purchase_order(db, purchase_order_id, actor, ip)


@router.post("/{purchase_order_id}/cancel", response_model=PurchaseOrderResponse)
def cancel_purchase_order(
    purchase_order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("purchase.orders.cancel")),
) -> PurchaseOrder:
    ip = request.client.host if request.client else None
    return service.cancel_purchase_order(db, purchase_order_id, actor, ip)
