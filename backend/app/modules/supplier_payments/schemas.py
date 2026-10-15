from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

PaymentNote = Annotated[str, StringConstraints(max_length=2000)]
PaymentReferenceType = Literal["RECEIPT", "DIRECT_PURCHASE"]


class SupplierPaymentAllocationCreate(BaseModel):
    ref_type: PaymentReferenceType
    ref_id: int = Field(ge=1)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2, allow_inf_nan=False)


class SupplierPaymentCreate(BaseModel):
    doc_date: date
    supplier_id: int = Field(ge=1)
    account_id: int = Field(ge=1)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2, allow_inf_nan=False)
    note: PaymentNote | None = None
    allocations: list[SupplierPaymentAllocationCreate] = Field(default_factory=list, max_length=100)


class SupplierPaymentAllocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ref_type: PaymentReferenceType
    ref_id: int
    amount: Decimal


class SupplierPaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doc_no: str
    doc_date: date
    supplier_id: int
    account_id: int
    amount: Decimal
    status: str
    note: str | None
    created_at: datetime
    allocations: list[SupplierPaymentAllocationResponse]


class SupplierPaymentBillOption(BaseModel):
    ref_type: PaymentReferenceType
    ref_id: int
    doc_no: str
    doc_date: date
    total: Decimal
    paid: Decimal
    outstanding: Decimal


class SupplierPaymentSupplierOption(BaseModel):
    id: int
    code: str
    name: str


class SupplierPaymentAccountOption(BaseModel):
    id: int
    name: str
    type: str


class SupplierPaymentOptionsResponse(BaseModel):
    suppliers: list[SupplierPaymentSupplierOption]
    accounts: list[SupplierPaymentAccountOption]
