from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.modules.inventory.models import MovementType


class StockBalanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    warehouse_id: int
    qty_on_hand: Decimal
    qty_reserved: Decimal
    available: Decimal
    updated_at: datetime


class WarehouseStockResponse(BaseModel):
    product_id: int
    product_sku: str
    product_name: str
    unit_code: str
    warehouse_id: int
    warehouse_code: str
    warehouse_name: str
    qty_on_hand: Decimal
    qty_reserved: Decimal
    available: Decimal


class StockTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    txn_date: datetime
    product_id: int
    warehouse_id: int
    movement_type: MovementType
    qty_signed: Decimal
    unit_cost: Decimal | None
    source_type: str | None
    source_id: int | None
    source_line_id: int | None
    note: str | None
    created_by: int | None
    created_at: datetime


class StockLedgerEntryResponse(StockTransactionResponse):
    running_qty: Decimal


class StockLedgerProductOption(BaseModel):
    id: int
    sku: str
    name: str
    unit_code: str


class StockLedgerWarehouseOption(BaseModel):
    id: int
    code: str
    name: str


class StockLedgerOptionsResponse(BaseModel):
    products: list[StockLedgerProductOption]
    warehouses: list[StockLedgerWarehouseOption]
