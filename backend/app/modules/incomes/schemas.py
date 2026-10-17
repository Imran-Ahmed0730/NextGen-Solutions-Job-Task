from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class IncomeCategoryOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class IncomeAccountOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    type: str


class IncomeOptionsResponse(BaseModel):
    categories: list[IncomeCategoryOption]
    accounts: list[IncomeAccountOption]


class IncomeCreate(BaseModel):
    doc_date: date
    category_id: int = Field(ge=1)
    account_id: int = Field(ge=1)
    amount: Decimal = Field(gt=0, le=Decimal("9999999999999999.99"))
    note: str | None = Field(default=None, max_length=1000)


class IncomeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    doc_no: str
    doc_date: date
    category_id: int
    account_id: int
    amount: Decimal
    status: str
    note: str | None
    created_at: datetime
