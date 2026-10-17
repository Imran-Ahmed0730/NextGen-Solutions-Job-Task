from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

CustomerCode = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]
CustomerName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
CustomerMobile = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=11,
        max_length=11,
        pattern=r"^01[3-9]\d{8}$",
    ),
]
CustomerEmail = Annotated[EmailStr, Field(max_length=255)]
CustomerAddress = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]
ContactDesignation = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]
PositiveId = Annotated[int, Field(strict=True, gt=0)]


class CustomerCreate(BaseModel):
    code: CustomerCode
    name: CustomerName
    mobile: CustomerMobile | None = None
    email: CustomerEmail | None = None
    address: CustomerAddress | None = None
    credit_limit: Decimal = Field(default=Decimal("0.00"), ge=0)
    opening_due: Decimal = Field(default=Decimal("0.00"))
    price_list_id: PositiveId | None = None
    is_active: bool = True


class CustomerUpdate(BaseModel):
    code: CustomerCode | None = None
    name: CustomerName | None = None
    mobile: CustomerMobile | None = None
    email: CustomerEmail | None = None
    address: CustomerAddress | None = None
    credit_limit: Decimal | None = Field(default=None, ge=0)
    opening_due: Decimal | None = None
    price_list_id: PositiveId | None = None
    is_active: bool | None = None


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    mobile: str | None
    email: str | None
    address: str | None
    credit_limit: Decimal
    opening_due: Decimal
    price_list_id: int | None
    is_active: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ContactCreate(BaseModel):
    name: CustomerName
    phone: CustomerMobile | None = None
    email: CustomerEmail | None = None
    designation: ContactDesignation | None = None


class ContactUpdate(BaseModel):
    name: CustomerName | None = None
    phone: CustomerMobile | None = None
    email: CustomerEmail | None = None
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
