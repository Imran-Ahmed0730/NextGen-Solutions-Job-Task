from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

PriceListName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
PositiveId = Annotated[int, Field(strict=True, gt=0)]


class PriceListCreate(BaseModel):
    name: PriceListName
    is_default: bool = False
    valid_from: date | None = None
    valid_to: date | None = None
    is_active: bool = True


class PriceListUpdate(BaseModel):
    name: PriceListName | None = None
    is_default: bool | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    is_active: bool | None = None


class PriceListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_default: bool
    valid_from: date | None
    valid_to: date | None
    is_active: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProductPriceCreate(BaseModel):
    product_id: PositiveId
    price: Decimal = Field(ge=0)


class ProductPriceUpdate(BaseModel):
    product_id: PositiveId | None = None
    price: Decimal | None = Field(default=None, ge=0)


class ProductPriceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    price_list_id: int
    product_id: int
    price: Decimal
    created_at: datetime
    updated_at: datetime