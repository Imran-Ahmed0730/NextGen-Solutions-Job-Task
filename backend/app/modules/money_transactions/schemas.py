from decimal import Decimal

from pydantic import BaseModel


class MoneyAccountBalanceResponse(BaseModel):
    account_id: int
    balance: Decimal
