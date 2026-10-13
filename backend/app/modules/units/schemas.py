from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

UnitName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
UnitCode = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]


class UnitCreate(BaseModel):
    name: UnitName
    code: UnitCode
    allow_decimal: bool = False


class UnitUpdate(BaseModel):
    name: UnitName | None = None
    code: UnitCode | None = None
    allow_decimal: bool | None = None


class UnitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    allow_decimal: bool
    is_active: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime
