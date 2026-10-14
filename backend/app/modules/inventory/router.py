from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.inventory import service
from app.modules.inventory.models import StockBalance
from app.modules.inventory.schemas import (
    StockBalanceResponse,
    StockLedgerEntryResponse,
    StockLedgerOptionsResponse,
    WarehouseStockResponse,
)

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


@router.get("/warehouse-stock", response_model=list[WarehouseStockResponse])
def list_warehouse_stock(
    search: str | None = Query(default=None, max_length=255),
    warehouse_id: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory.stock.read")),
) -> list[WarehouseStockResponse]:
    return service.list_warehouse_stock(
        db,
        search=search,
        warehouse_id=warehouse_id,
        offset=offset,
        limit=limit,
    )


@router.get("/ledger/options", response_model=StockLedgerOptionsResponse)
def get_stock_ledger_options(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory.stock.read")),
) -> StockLedgerOptionsResponse:
    return service.get_stock_ledger_options(db)


@router.get("/ledger", response_model=list[StockLedgerEntryResponse])
def list_stock_ledger(
    product_id: int = Query(ge=1),
    warehouse_id: int | None = Query(default=None, ge=1),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory.stock.read")),
) -> list[StockLedgerEntryResponse]:
    return service.list_stock_ledger(
        db,
        product_id=product_id,
        warehouse_id=warehouse_id,
        date_from=date_from,
        date_to=date_to,
        offset=offset,
        limit=limit,
    )
