from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

SupplierCode = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)
]
SupplierName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
PositiveId = Annotated[int, Field(strict=True, gt=0)]


class SupplierCreate(BaseModel):
    code: SupplierCode
    name: SupplierName
    mobile: str | None = None
    email: str | None = None
    address: str | None = None
    opening_due: Decimal = Field(default=Decimal("0.00"))
    is_active: bool = True


class SupplierUpdate(BaseModel):
    code: SupplierCode | None = None
    name: SupplierName | None = None
    mobile: str | None = None
    email: str | None = None
    address: str | None = None
    opening_due: Decimal | None = None
    is_active: bool | None = None


class SupplierResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    mobile: str | None
    email: str | None
    address: str | None
    opening_due: Decimal
    is_active: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ContactCreate(BaseModel):
    name: SupplierName
    phone: str | None = None
    email: str | None = None
    designation: str | None = None


class ContactUpdate(BaseModel):
    name: SupplierName | None = None
    phone: str | None = None
    email: str | None = None
    designation: str | None = None


class ContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    party_type: str
    party_id: int
    name: str
    phone: str | None
    email: str | None
    designation: str | None