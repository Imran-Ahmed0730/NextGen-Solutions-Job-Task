from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

AdjustmentReason = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]
AdjustmentQuantity = Annotated[
    Decimal,
    Field(max_digits=18, decimal_places=3, allow_inf_nan=False),
]


class StockAdjustmentLineCreate(BaseModel):
    product_id: int = Field(ge=1)
    qty_signed: AdjustmentQuantity


class StockAdjustmentCreate(BaseModel):
    doc_date: date
    warehouse_id: int = Field(ge=1)
    reason: AdjustmentReason
    lines: list[StockAdjustmentLineCreate] = Field(min_length=1, max_length=500)


class StockAdjustmentLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    qty_signed: Decimal
    unit_cost: Decimal


class StockAdjustmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doc_no: str
    doc_date: date
    warehouse_id: int
    reason: str
    status: str
    lines: list[StockAdjustmentLineResponse]


class AdjustmentWarehouseOption(BaseModel):
    id: int
    code: str
    name: str


class AdjustmentProductOption(BaseModel):
    id: int
    sku: str
    name: str
    unit_code: str | None
    is_stocked: bool


class StockAdjustmentOptionsResponse(BaseModel):
    warehouses: list[AdjustmentWarehouseOption]
    products: list[AdjustmentProductOption]
