from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

CategoryName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]


class ProductCategoryCreate(BaseModel):
    name: CategoryName
    parent_id: int | None = None
    is_active: bool = True


class ProductCategoryUpdate(BaseModel):
    name: CategoryName | None = None
    parent_id: int | None = None
    is_active: bool = True


class ProductCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    parent_id: int | None
    is_active: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime
