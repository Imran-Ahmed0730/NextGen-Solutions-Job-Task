from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

PurchaseReturnNote = Annotated[str, StringConstraints(max_length=2000)]


class PurchaseReturnLineInput(BaseModel):
    receipt_line_id: int = Field(ge=1)
    qty: Decimal = Field(gt=0, max_digits=18, decimal_places=3, allow_inf_nan=False)


class PurchaseReturnCreate(BaseModel):
    doc_date: date
    receipt_id: int = Field(ge=1)
    note: PurchaseReturnNote | None = None
    lines: list[PurchaseReturnLineInput] = Field(min_length=1, max_length=500)


class PurchaseReturnLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    receipt_line_id: int
    product_id: int
    product_sku: str
    product_name: str
    qty: Decimal
    unit_cost: Decimal
    line_total: Decimal


class PurchaseReturnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doc_no: str
    doc_date: date
    receipt_id: int
    receipt_doc_no: str
    supplier_id: int
    warehouse_id: int
    status: str
    total: Decimal
    note: str | None
    lines: list[PurchaseReturnLineResponse]


class PurchaseReturnReceiptLineOption(BaseModel):
    receipt_line_id: int
    product_id: int
    product_sku: str
    product_name: str
    unit_code: str
    allow_decimal: bool
    qty_received: Decimal
    qty_returned: Decimal
    qty_available: Decimal
    unit_cost: Decimal


class PurchaseReturnReceiptOption(BaseModel):
    id: int
    doc_no: str
    doc_date: date
    supplier_id: int
    supplier_name: str
    warehouse_id: int
    warehouse_name: str
    lines: list[PurchaseReturnReceiptLineOption]


class PurchaseReturnOptionsResponse(BaseModel):
    receipts: list[PurchaseReturnReceiptOption]
