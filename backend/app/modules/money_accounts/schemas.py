from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.modules.money_accounts.models import MoneyAccountType

MoneyAccountName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
AccountNo = Annotated[str, StringConstraints(strip_whitespace=True, max_length=50)]
PositiveId = Annotated[int, Field(strict=True, gt=0)]


class MoneyAccountCreate(BaseModel):
    name: MoneyAccountName
    type: MoneyAccountType
    payment_method_id: PositiveId | None = None
    account_no: AccountNo | None = None
    opening_balance: Decimal = Field(default=Decimal("0.00"))
    allow_overdraft: bool = False
    is_active: bool = True


class MoneyAccountUpdate(BaseModel):
    name: MoneyAccountName | None = None
    type: MoneyAccountType | None = None
    payment_method_id: PositiveId | None = None
    account_no: AccountNo | None = None
    opening_balance: Decimal | None = Field(default=None)
    allow_overdraft: bool | None = None
    is_active: bool | None = None


class MoneyAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: MoneyAccountType
    payment_method_id: int | None
    account_no: str | None
    opening_balance: Decimal
    allow_overdraft: bool
    is_active: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime