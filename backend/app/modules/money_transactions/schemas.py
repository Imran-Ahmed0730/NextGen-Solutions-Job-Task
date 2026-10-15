from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class MoneyAccountBalanceResponse(BaseModel):
    account_id: int
    balance: Decimal


class MoneyAccountBalanceItem(BaseModel):
    account_id: int
    account_name: str
    account_type: str
    opening_balance: Decimal
    balance: Decimal


class LedgerEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    txn_date: datetime
    amount_signed: Decimal
    txn_type: str
    source_type: str | None
    source_id: int | None
    party_type: str | None
    party_id: int | None
    note: str | None
    running_balance: Decimal


class AccountLedgerResponse(BaseModel):
    account_id: int
    account_name: str
    opening_balance: Decimal
    closing_balance: Decimal
    total_inflow: Decimal
    total_outflow: Decimal
    entries: list[LedgerEntry]
