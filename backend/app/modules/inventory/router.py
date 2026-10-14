from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.inventory import service
from app.modules.inventory.models import StockBalance, StockTransaction
from app.modules.inventory.schemas import StockBalanceResponse, StockTransactionResponse

router = APIRouter(prefix="/api/v1/inventory", tags=["inventory"])


@router.get("/stock", response_model=list[StockBalanceResponse])
def list_stock(
    product_id: int | None = Query(default=None, ge=1),
    warehouse_id: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory.stock.read")),
) -> list[StockBalance]:
    return service.list_stock(
        db,
        product_id=product_id,
        warehouse_id=warehouse_id,
        offset=offset,
        limit=limit,
    )


@router.get("/ledger", response_model=list[StockTransactionResponse])
def list_stock_ledger(
    product_id: int = Query(ge=1),
    warehouse_id: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory.stock.read")),
) -> list[StockTransaction]:
    return service.list_stock_ledger(
        db,
        product_id=product_id,
        warehouse_id=warehouse_id,
        offset=offset,
        limit=limit,
    )
