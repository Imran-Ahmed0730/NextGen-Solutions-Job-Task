from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

MoneyAmount = Annotated[
    Decimal, Field(ge=0, max_digits=18, decimal_places=2, allow_inf_nan=False)
]


class PayrollRunCreate(BaseModel):
    period_month: int = Field(ge=1, le=12)
    period_year: int = Field(ge=2000, le=9999)


class PayrollLineUpdate(BaseModel):
    deductions: MoneyAmount


class PayrollPost(BaseModel):
    account_id: int = Field(ge=1)
    paid_on: date


class PayrollEmployeeResponse(BaseModel):
    id: int
    code: str
    name: str
    department: str | None


class PayrollLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    employee: PayrollEmployeeResponse
    base_salary: Decimal
    deductions: Decimal
    net_pay: Decimal
    paid_txn_id: int | None


class PayrollRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doc_no: str | None
    period_month: int
    period_year: int
    status: str
    total_amount: Decimal
    paid_on: date | None
    account_id: int | None
    created_at: datetime
    lines: list[PayrollLineResponse]


class PayrollAccountOption(BaseModel):
    id: int
    name: str
    type: str


class PayrollOptionsResponse(BaseModel):
    accounts: list[PayrollAccountOption]
