from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.stock_transfers import service
from app.modules.stock_transfers.models import StockTransfer
from app.modules.stock_transfers.schemas import (
    StockTransferCreate,
    StockTransferOptionsResponse,
    StockTransferResponse,
)

router = APIRouter(prefix="/api/v1/inventory/transfers", tags=["stock-transfers"])


@router.get("/options", response_model=StockTransferOptionsResponse)
def get_transfer_options(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory.transfers.read")),
) -> StockTransferOptionsResponse:
    return service.get_transfer_options(db)


@router.get("", response_model=list[StockTransferResponse])
def list_transfers(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory.transfers.read")),
) -> list[StockTransfer]:
    return service.list_transfers(db, offset=offset, limit=limit)


@router.post("", response_model=StockTransferResponse, status_code=status.HTTP_201_CREATED)
def post_transfer(
    payload: StockTransferCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("inventory.transfers.create")),
) -> StockTransfer:
    ip = request.client.host if request.client else None
    return service.post_transfer(db, payload, actor, ip)


@router.get("/{transfer_id}", response_model=StockTransferResponse)
def get_transfer(
    transfer_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory.transfers.read")),
) -> StockTransfer:
    transfer = service.get_transfer(db, transfer_id)
    if transfer is None:
        raise HTTPException(status_code=404, detail="Stock transfer not found")
    return transfer
