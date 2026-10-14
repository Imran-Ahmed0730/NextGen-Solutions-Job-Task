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
