from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

DirectPurchaseNote = Annotated[str, StringConstraints(max_length=2000)]


class DirectPurchaseLineInput(BaseModel):
    product_id: int = Field(ge=1)
    qty: Decimal = Field(gt=0, max_digits=18, decimal_places=3, allow_inf_nan=False)
    unit_cost: Decimal = Field(ge=0, max_digits=18, decimal_places=4, allow_inf_nan=False)


class DirectPurchaseCreate(BaseModel):
    doc_date: date
    supplier_id: int = Field(ge=1)
    warehouse_id: int = Field(ge=1)
    note: DirectPurchaseNote | None = None
    lines: list[DirectPurchaseLineInput] = Field(min_length=1, max_length=500)


class DirectPurchaseLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    product_sku: str
    product_name: str
    qty: Decimal
    unit_cost: Decimal
    line_total: Decimal


class DirectPurchaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doc_no: str
    doc_date: date
    supplier_id: int
    warehouse_id: int
    status: str
    total: Decimal
    paid_amount: Decimal
    money_account_id: int | None
    note: str | None
    lines: list[DirectPurchaseLineResponse]


class DirectPurchaseSupplierOption(BaseModel):
    id: int
    code: str
    name: str


class DirectPurchaseWarehouseOption(BaseModel):
    id: int
    code: str
    name: str


class DirectPurchaseProductOption(BaseModel):
    id: int
    sku: str
    name: str
    unit_code: str
    allow_decimal: bool


class DirectPurchaseOptionsResponse(BaseModel):
    suppliers: list[DirectPurchaseSupplierOption]
    warehouses: list[DirectPurchaseWarehouseOption]
    products: list[DirectPurchaseProductOption]
