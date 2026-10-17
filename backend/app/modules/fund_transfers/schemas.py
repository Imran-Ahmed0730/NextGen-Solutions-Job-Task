from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TransferAccountOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    type: str


class FundTransferOptionsResponse(BaseModel):
    accounts: list[TransferAccountOption]


class FundTransferCreate(BaseModel):
    doc_date: date
    from_account_id: int = Field(ge=1)
    to_account_id: int = Field(ge=1)
    amount: Decimal = Field(gt=0, le=Decimal("9999999999999999.99"))
    note: str | None = Field(default=None, max_length=1000)


class FundTransferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    doc_no: str
    doc_date: date
    from_account_id: int
    to_account_id: int
    amount: Decimal
    status: str
    note: str | None
    created_at: datetime
