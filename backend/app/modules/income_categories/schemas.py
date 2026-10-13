from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

CategoryName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]


class IncomeCategoryCreate(BaseModel):
    name: CategoryName
    is_active: bool = True


class IncomeCategoryUpdate(BaseModel):
    name: CategoryName | None = None
    is_active: bool | None = None


class IncomeCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_active: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime