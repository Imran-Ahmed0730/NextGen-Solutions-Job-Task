from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

GoodsReceiptNote = Annotated[str, StringConstraints(max_length=2000)]


class GoodsReceiptLineInput(BaseModel):
    po_line_id: int = Field(ge=1)
    qty: Decimal = Field(gt=0, max_digits=18, decimal_places=3, allow_inf_nan=False)
    unit_cost: Decimal = Field(ge=0, max_digits=18, decimal_places=4, allow_inf_nan=False)


class GoodsReceiptCreate(BaseModel):
    doc_date: date
    po_id: int = Field(ge=1)
    note: GoodsReceiptNote | None = None
    lines: list[GoodsReceiptLineInput] = Field(min_length=1, max_length=500)


class GoodsReceiptLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    po_line_id: int
    product_id: int
    product_sku: str
    product_name: str
    qty: Decimal
    unit_cost: Decimal
    line_total: Decimal


class GoodsReceiptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doc_no: str
    doc_date: date
    po_id: int
    supplier_id: int
    warehouse_id: int
    status: str
    total: Decimal
    note: str | None
    lines: list[GoodsReceiptLineResponse]


class GoodsReceiptOrderLineOption(BaseModel):
    po_line_id: int
    product_id: int
    product_sku: str
    product_name: str
    unit_code: str
    allow_decimal: bool
    qty_ordered: Decimal
    received_qty: Decimal
    unit_price: Decimal


class GoodsReceiptOrderOption(BaseModel):
    id: int
    doc_no: str
    doc_date: date
    supplier_id: int
    supplier_name: str
    warehouse_id: int
    warehouse_name: str
    status: str
    lines: list[GoodsReceiptOrderLineOption]


class GoodsReceiptOptionsResponse(BaseModel):
    orders: list[GoodsReceiptOrderOption]
