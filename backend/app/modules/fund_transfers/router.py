from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.fund_transfers import service
from app.modules.fund_transfers.models import FundTransfer
from app.modules.fund_transfers.schemas import (
    FundTransferCreate,
    FundTransferOptionsResponse,
    FundTransferResponse,
)

router = APIRouter(prefix="/api/v1/fund-transfers", tags=["fund-transfers"])


@router.get("/options", response_model=FundTransferOptionsResponse)
def get_transfer_options(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("money.transfers.read")),
) -> FundTransferOptionsResponse:
    return service.get_transfer_options(db)


@router.get("", response_model=list[FundTransferResponse])
def list_transfers(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("money.transfers.read")),
) -> list[FundTransfer]:
    return service.list_transfers(db, offset=offset, limit=limit)


@router.post("", response_model=FundTransferResponse, status_code=status.HTTP_201_CREATED)
def create_transfer(
    payload: FundTransferCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("money.transfers.create")),
) -> FundTransfer:
    ip = request.client.host if request.client else None
    return service.create_transfer(db, payload, actor, ip)


@router.get("/{transfer_id}", response_model=FundTransferResponse)
def get_transfer(
    transfer_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("money.transfers.read")),
) -> FundTransfer:
    transfer = service.get_transfer(db, transfer_id)
    if transfer is None:
        raise HTTPException(status_code=404, detail="Fund transfer not found")
    return transfer
