from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

TransferNote = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]
TransferQuantity = Annotated[
    Decimal,
    Field(gt=0, max_digits=18, decimal_places=3),
]


class StockTransferLineCreate(BaseModel):
    product_id: int = Field(ge=1)
    qty: TransferQuantity


class StockTransferCreate(BaseModel):
    doc_date: date
    from_warehouse_id: int = Field(ge=1)
    to_warehouse_id: int = Field(ge=1)
    lines: list[StockTransferLineCreate] = Field(min_length=1, max_length=500)
    note: TransferNote | None = None


class StockTransferLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    qty: Decimal


class StockTransferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doc_no: str
    doc_date: date
    from_warehouse_id: int
    to_warehouse_id: int
    status: str
    note: str | None
    lines: list[StockTransferLineResponse]


class TransferWarehouseOption(BaseModel):
    id: int
    code: str
    name: str


class TransferProductOption(BaseModel):
    id: int
    sku: str
    name: str
    unit_code: str | None
    is_stocked: bool


class StockTransferOptionsResponse(BaseModel):
    warehouses: list[TransferWarehouseOption]
    products: list[TransferProductOption]
