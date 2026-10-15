from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

SalesReturnNote = Annotated[str, StringConstraints(max_length=2000)]


class SalesReturnLineInput(BaseModel):
    invoice_line_id: int = Field(ge=1)
    qty: Decimal = Field(gt=0, max_digits=18, decimal_places=3, allow_inf_nan=False)


class SalesReturnCreate(BaseModel):
    doc_date: date
    invoice_id: int = Field(ge=1)
    note: SalesReturnNote | None = None
    lines: list[SalesReturnLineInput] = Field(min_length=1, max_length=500)


class SalesReturnLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_line_id: int
    product_id: int
    product_sku: str
    product_name: str
    qty: Decimal
    unit_code: str
    unit_price: Decimal
    line_total: Decimal
    unit_cost_cogs: Decimal


class SalesReturnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doc_no: str
    doc_date: date
    invoice_id: int
    invoice_doc_no: str
    customer_id: int
    warehouse_id: int
    status: str
    total: Decimal
    note: str | None
    lines: list[SalesReturnLineResponse]


class SalesReturnInvoiceLineOption(BaseModel):
    invoice_line_id: int
    product_id: int
    product_sku: str
    product_name: str
    unit_code: str
    allow_decimal: bool
    qty_invoiced: Decimal
    qty_returned: Decimal
    qty_available: Decimal
    unit_price: Decimal
    unit_cost_cogs: Decimal


class SalesReturnInvoiceOption(BaseModel):
    id: int
    doc_no: str
    doc_date: date
    lines: list[SalesReturnInvoiceLineOption]


class SalesReturnOptionsResponse(BaseModel):
    invoices: list[SalesReturnInvoiceOption]
