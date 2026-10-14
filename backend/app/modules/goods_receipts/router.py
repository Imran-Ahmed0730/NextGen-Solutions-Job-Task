from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.goods_receipts import service
from app.modules.goods_receipts.models import GoodsReceipt
from app.modules.goods_receipts.schemas import (
    GoodsReceiptCreate,
    GoodsReceiptOptionsResponse,
    GoodsReceiptResponse,
)

router = APIRouter(prefix="/api/v1/purchase/receipts", tags=["goods-receipts"])


@router.get("/options", response_model=GoodsReceiptOptionsResponse)
def get_receipt_options(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("purchase.receipts.read")),
) -> GoodsReceiptOptionsResponse:
    return service.get_receipt_options(db)


@router.get("", response_model=list[GoodsReceiptResponse])
def list_receipts(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("purchase.receipts.read")),
) -> list[GoodsReceipt]:
    return service.list_receipts(db, offset=offset, limit=limit)


@router.post("", response_model=GoodsReceiptResponse, status_code=status.HTTP_201_CREATED)
def create_receipt(
    payload: GoodsReceiptCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("purchase.receipts.create")),
) -> GoodsReceipt:
    ip = request.client.host if request.client else None
    return service.create_goods_receipt(db, payload, actor, ip)


@router.get("/{receipt_id}", response_model=GoodsReceiptResponse)
def get_receipt(
    receipt_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("purchase.receipts.read")),
) -> GoodsReceipt:
    receipt = service.get_receipt(db, receipt_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="Goods receipt not found")
    return receipt
