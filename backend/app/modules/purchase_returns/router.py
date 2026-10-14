from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.purchase_returns import service
from app.modules.purchase_returns.models import PurchaseReturn
from app.modules.purchase_returns.schemas import (
    PurchaseReturnCreate,
    PurchaseReturnOptionsResponse,
    PurchaseReturnResponse,
)

router = APIRouter(prefix="/api/v1/purchase/returns", tags=["purchase-returns"])


@router.get("/options", response_model=PurchaseReturnOptionsResponse)
def get_purchase_return_options(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("purchase.returns.read")),
) -> PurchaseReturnOptionsResponse:
    return service.get_purchase_return_options(db)


@router.get("", response_model=list[PurchaseReturnResponse])
def list_purchase_returns(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("purchase.returns.read")),
) -> list[PurchaseReturn]:
    return service.list_purchase_returns(db, offset=offset, limit=limit)


@router.post("", response_model=PurchaseReturnResponse, status_code=status.HTTP_201_CREATED)
def create_purchase_return(
    payload: PurchaseReturnCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("purchase.returns.create")),
) -> PurchaseReturn:
    ip = request.client.host if request.client else None
    return service.create_purchase_return(db, payload, actor, ip)


@router.get("/{return_id}", response_model=PurchaseReturnResponse)
def get_purchase_return(
    return_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("purchase.returns.read")),
) -> PurchaseReturn:
    purchase_return = service.get_purchase_return(db, return_id)
    if purchase_return is None:
        raise HTTPException(status_code=404, detail="Purchase return not found")
    return purchase_return
