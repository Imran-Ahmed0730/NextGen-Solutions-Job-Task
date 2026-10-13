from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

WarehouseName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
WarehouseCode = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)
]
WarehouseAddress = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=255)
]


class WarehouseCreate(BaseModel):
    name: WarehouseName
    code: WarehouseCode
    address: WarehouseAddress | None = None
    is_default: bool = False
    is_active: bool = True


class WarehouseUpdate(BaseModel):
    name: WarehouseName | None = None
    code: WarehouseCode | None = None
    address: WarehouseAddress | None = None
    is_default: bool | None = None
    is_active: bool | None = None


class WarehouseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    address: str | None
    is_default: bool
    is_active: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime
