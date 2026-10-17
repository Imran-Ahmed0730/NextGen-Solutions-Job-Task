from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

CategoryName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
ParentCategoryId = Annotated[int, Field(strict=True, gt=0)]


class ExpenseCategoryCreate(BaseModel):
    name: CategoryName
    parent_id: ParentCategoryId | None = None
    is_active: bool = True


class ExpenseCategoryUpdate(BaseModel):
    name: CategoryName | None = None
    parent_id: ParentCategoryId | None = None
    is_active: bool | None = None


class ExpenseCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    parent_id: int | None
    is_active: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime
