from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

SupplierCode = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)
]
SupplierName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
SupplierMobile = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=11,
        max_length=11,
        pattern=r"^01[3-9]\d{8}$",
    ),
]
SupplierEmail = Annotated[EmailStr, Field(max_length=255)]
SupplierAddress = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]
ContactDesignation = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]
PositiveId = Annotated[int, Field(strict=True, gt=0)]


class SupplierCreate(BaseModel):
    code: SupplierCode
    name: SupplierName
    mobile: SupplierMobile | None = None
    email: SupplierEmail | None = None
    address: SupplierAddress | None = None
    opening_due: Decimal = Field(default=Decimal("0.00"))
    is_active: bool = True


class SupplierUpdate(BaseModel):
    code: SupplierCode | None = None
    name: SupplierName | None = None
    mobile: SupplierMobile | None = None
    email: SupplierEmail | None = None
    address: SupplierAddress | None = None
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
    phone: SupplierMobile | None = None
    email: SupplierEmail | None = None
    designation: ContactDesignation | None = None


class ContactUpdate(BaseModel):
    name: SupplierName | None = None
    phone: SupplierMobile | None = None
    email: SupplierEmail | None = None
    designation: ContactDesignation | None = None


class ContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    party_type: str
    party_id: int
    name: str
    phone: str | None
    email: str | None
    designation: str | None