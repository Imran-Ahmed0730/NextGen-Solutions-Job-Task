from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.sales.models import SalesOrder
from app.modules.sales_orders import service
from app.modules.sales_orders.schemas import (
    SalesOrderCreate,
    SalesOrderOptionsResponse,
    SalesOrderResponse,
    SalesOrderUpdate,
)

router = APIRouter(prefix="/api/v1/sales/orders", tags=["sales-orders"])


@router.get("/options", response_model=SalesOrderOptionsResponse)
def get_sales_order_options(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sales.orders.read")),
) -> SalesOrderOptionsResponse:
    return service.get_sales_order_options(db)


@router.get("", response_model=list[SalesOrderResponse])
def list_sales_orders(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sales.orders.read")),
) -> list[SalesOrder]:
    return service.list_sales_orders(db, offset=offset, limit=limit)


@router.post("", response_model=SalesOrderResponse, status_code=status.HTTP_201_CREATED)
def create_sales_order(
    payload: SalesOrderCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("sales.orders.create")),
) -> SalesOrder:
    ip = request.client.host if request.client else None
    return service.create_sales_order(db, payload, actor, ip)


@router.get("/{sales_order_id}", response_model=SalesOrderResponse)
def get_sales_order(
    sales_order_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sales.orders.read")),
) -> SalesOrder:
    order = service.get_sales_order(db, sales_order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Sales order not found")
    return order


@router.put("/{sales_order_id}", response_model=SalesOrderResponse)
def update_sales_order(
    sales_order_id: int,
    payload: SalesOrderUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("sales.orders.update")),
) -> SalesOrder:
    ip = request.client.host if request.client else None
    return service.update_sales_order(db, sales_order_id, payload, actor, ip)
