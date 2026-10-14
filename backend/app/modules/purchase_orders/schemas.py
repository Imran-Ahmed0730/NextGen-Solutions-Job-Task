from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

PurchaseOrderNote = Annotated[str, StringConstraints(max_length=2000)]


class PurchaseOrderLineInput(BaseModel):
    product_id: int = Field(ge=1)
    qty: Decimal = Field(max_digits=18, decimal_places=3, allow_inf_nan=False)
    unit_price: Decimal = Field(max_digits=18, decimal_places=2, allow_inf_nan=False)


class PurchaseOrderCreate(BaseModel):
    doc_date: date
    supplier_id: int = Field(ge=1)
    warehouse_id: int = Field(ge=1)
    expected_date: date | None = None
    discount: Decimal = Field(default=Decimal("0.00"), max_digits=18, decimal_places=2)
    note: PurchaseOrderNote | None = None
    lines: list[PurchaseOrderLineInput] = Field(min_length=1, max_length=500)


class PurchaseOrderUpdate(PurchaseOrderCreate):
    pass


class PurchaseOrderLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    qty: Decimal
    unit_price: Decimal
    line_total: Decimal
    received_qty: Decimal


class PurchaseOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doc_no: str
    doc_date: date
    supplier_id: int
    warehouse_id: int
    status: str
    expected_date: date | None
    subtotal: Decimal
    discount: Decimal
    total: Decimal
    note: str | None
    lines: list[PurchaseOrderLineResponse]


class PurchaseOrderSupplierOption(BaseModel):
    id: int
    code: str
    name: str


class PurchaseOrderWarehouseOption(BaseModel):
    id: int
    code: str
    name: str


class PurchaseOrderProductOption(BaseModel):
    id: int
    sku: str
    name: str
    unit_code: str
    allow_decimal: bool


class PurchaseOrderOptionsResponse(BaseModel):
    suppliers: list[PurchaseOrderSupplierOption]
    warehouses: list[PurchaseOrderWarehouseOption]
    products: list[PurchaseOrderProductOption]
