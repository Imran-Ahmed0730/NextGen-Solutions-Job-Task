from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.modules.products.models import ProductType

ProductSku = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=50,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    ),
]
ProductName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
ProductDescription = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]
PositiveId = Annotated[int, Field(strict=True, gt=0)]


class ProductCreate(BaseModel):
    sku: ProductSku
    name: ProductName
    type: ProductType
    category_id: PositiveId
    unit_id: PositiveId
    is_stocked: bool = True
    reorder_level: Decimal = Field(default=Decimal("0.000"), ge=0)
    sales_price_default: Decimal = Field(default=Decimal("0.00"), ge=0)
    description: ProductDescription | None = None
    is_active: bool = True


class ProductUpdate(BaseModel):
    sku: ProductSku | None = None
    name: ProductName | None = None
    type: ProductType | None = None
    category_id: PositiveId | None = None
    unit_id: PositiveId | None = None
    is_stocked: bool | None = None
    reorder_level: Decimal | None = Field(default=None, ge=0)
    sales_price_default: Decimal | None = Field(default=None, ge=0)
    description: ProductDescription | None = None
    is_active: bool | None = None


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
    type: ProductType
    category_id: int
    category_name: str | None = None
    unit_id: int
    unit_name: str | None = None
    unit_code: str | None = None
    is_stocked: bool
    reorder_level: Decimal
    avg_cost: Decimal
    sales_price_default: Decimal
    description: str | None
    is_active: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime
