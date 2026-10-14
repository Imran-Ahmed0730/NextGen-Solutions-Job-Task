from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.direct_purchases import service
from app.modules.direct_purchases.models import DirectPurchase
from app.modules.direct_purchases.schemas import (
    DirectPurchaseCreate,
    DirectPurchaseOptionsResponse,
    DirectPurchaseResponse,
)

router = APIRouter(prefix="/api/v1/purchase/direct-purchases", tags=["direct-purchases"])


@router.get("/options", response_model=DirectPurchaseOptionsResponse)
def get_direct_purchase_options(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("purchase.direct_purchases.read")),
) -> DirectPurchaseOptionsResponse:
    return service.get_direct_purchase_options(db)


@router.get("", response_model=list[DirectPurchaseResponse])
def list_direct_purchases(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("purchase.direct_purchases.read")),
) -> list[DirectPurchase]:
    return service.list_direct_purchases(db, offset=offset, limit=limit)


@router.post("", response_model=DirectPurchaseResponse, status_code=status.HTTP_201_CREATED)
def create_direct_purchase(
    payload: DirectPurchaseCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("purchase.direct_purchases.create")),
) -> DirectPurchase:
    ip = request.client.host if request.client else None
    return service.create_direct_purchase(db, payload, actor, ip)


@router.get("/{purchase_id}", response_model=DirectPurchaseResponse)
def get_direct_purchase(
    purchase_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("purchase.direct_purchases.read")),
) -> DirectPurchase:
    purchase = service.get_direct_purchase(db, purchase_id)
    if purchase is None:
        raise HTTPException(status_code=404, detail="Direct purchase not found")
    return purchase
