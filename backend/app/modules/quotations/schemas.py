from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

QuotationNote = Annotated[str, StringConstraints(max_length=2000)]


class QuotationLineInput(BaseModel):
    product_id: int = Field(ge=1)
    qty: Decimal = Field(gt=0, max_digits=18, decimal_places=3, allow_inf_nan=False)
    unit_price: Decimal = Field(ge=0, max_digits=18, decimal_places=2, allow_inf_nan=False)


class QuotationCreate(BaseModel):
    doc_date: date
    customer_id: int = Field(ge=1)
    valid_until: date | None = None
    discount: Decimal = Field(
        default=Decimal("0.00"), ge=0, max_digits=18, decimal_places=2, allow_inf_nan=False
    )
    note: QuotationNote | None = None
    lines: list[QuotationLineInput] = Field(min_length=1, max_length=500)


class QuotationUpdate(QuotationCreate):
    pass


class QuotationLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    qty: Decimal
    unit_price: Decimal
    line_total: Decimal


class QuotationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doc_no: str
    doc_date: date
    customer_id: int
    valid_until: date | None
    status: str
    subtotal: Decimal
    discount: Decimal
    total: Decimal
    note: str | None
    lines: list[QuotationLineResponse]


class QuotationCustomerOption(BaseModel):
    id: int
    code: str
    name: str


class QuotationProductOption(BaseModel):
    id: int
    sku: str
    name: str
    unit_code: str
    allow_decimal: bool


class QuotationOptionsResponse(BaseModel):
    customers: list[QuotationCustomerOption]
    products: list[QuotationProductOption]
