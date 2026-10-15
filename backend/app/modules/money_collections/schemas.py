from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

CollectionNote = Annotated[str, StringConstraints(max_length=2000)]
MethodReference = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]


class CustomerCollectionCreate(BaseModel):
    doc_date: date
    customer_id: int = Field(ge=1)
    account_id: int = Field(ge=1)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2, allow_inf_nan=False)
    method_ref: MethodReference | None = None
    note: CollectionNote | None = None


class CustomerCollectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doc_no: str
    doc_date: date
    customer_id: int
    account_id: int
    amount: Decimal
    method_ref: str | None
    status: str
    note: str | None
    created_at: datetime


class CollectionCustomerOption(BaseModel):
    id: int
    code: str
    name: str


class CollectionAccountOption(BaseModel):
    id: int
    name: str
    type: str


class CustomerCollectionOptionsResponse(BaseModel):
    customers: list[CollectionCustomerOption]
    accounts: list[CollectionAccountOption]
