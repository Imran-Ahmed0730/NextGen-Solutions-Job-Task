from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ExpenseCategoryOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class ExpenseAccountOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    type: str


class ExpenseOptionsResponse(BaseModel):
    categories: list[ExpenseCategoryOption]
    accounts: list[ExpenseAccountOption]


class ExpenseCreate(BaseModel):
    doc_date: date
    category_id: int = Field(ge=1)
    account_id: int = Field(ge=1)
    amount: Decimal = Field(gt=0, le=Decimal("9999999999999999.99"))
    paid_to: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=1000)


class ExpenseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    doc_no: str
    doc_date: date
    category_id: int
    account_id: int
    amount: Decimal
    paid_to: str | None
    status: str
    note: str | None
    created_at: datetime
