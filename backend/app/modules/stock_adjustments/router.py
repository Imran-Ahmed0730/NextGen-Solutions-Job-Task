from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.stock_adjustments import service
from app.modules.stock_adjustments.models import StockAdjustment
from app.modules.stock_adjustments.schemas import (
    StockAdjustmentCreate,
    StockAdjustmentOptionsResponse,
    StockAdjustmentResponse,
)

router = APIRouter(prefix="/api/v1/inventory/adjustments", tags=["stock-adjustments"])


@router.get("/options", response_model=StockAdjustmentOptionsResponse)
def get_adjustment_options(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory.adjustments.read")),
) -> StockAdjustmentOptionsResponse:
    return service.get_adjustment_options(db)


@router.get("", response_model=list[StockAdjustmentResponse])
def list_adjustments(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory.adjustments.read")),
) -> list[StockAdjustment]:
    return service.list_adjustments(db, offset=offset, limit=limit)


@router.post("", response_model=StockAdjustmentResponse, status_code=status.HTTP_201_CREATED)
def post_adjustment(
    payload: StockAdjustmentCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("inventory.adjustments.create")),
) -> StockAdjustment:
    ip = request.client.host if request.client else None
    return service.post_adjustment(db, payload, actor, ip)


@router.get("/{adjustment_id}", response_model=StockAdjustmentResponse)
def get_adjustment(
    adjustment_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory.adjustments.read")),
) -> StockAdjustment:
    adjustment = service.get_adjustment(db, adjustment_id)
    if adjustment is None:
        raise HTTPException(status_code=404, detail="Stock adjustment not found")
    return adjustment


@router.put("/{adjustment_id}", response_model=StockAdjustmentResponse)
def update_rejected_adjustment(
    adjustment_id: int,
    payload: StockAdjustmentCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("inventory.adjustments.update")),
) -> StockAdjustment:
    ip = request.client.host if request.client else None
    return service.update_rejected_adjustment(db, adjustment_id, payload, actor, ip)
