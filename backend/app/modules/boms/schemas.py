from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.modules.products.models import ProductType

BOMCode = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)
]
Quantity = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=3)]
Cost = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)]


class BOMLineInput(BaseModel):
    raw_product_id: int = Field(gt=0)
    qty: Quantity


class BOMCreate(BaseModel):
    code: BOMCode
    finished_product_id: int = Field(gt=0)
    output_qty: Quantity
    labor_cost_default: Cost = Decimal("0.00")
    overhead_cost_default: Cost = Decimal("0.00")
    lines: list[BOMLineInput] = Field(min_length=1, max_length=500)

class BOMLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    raw_product_id: int
    qty: Decimal


class BOMResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    finished_product_id: int
    output_qty: Decimal
    labor_cost_default: Decimal
    overhead_cost_default: Decimal
    is_active: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    lines: list[BOMLineResponse]


class BOMProductOption(BaseModel):
    id: int
    sku: str
    name: str
    unit_code: str
    type: ProductType


class BOMOptionsResponse(BaseModel):
    raw_products: list[BOMProductOption]
    finished_products: list[BOMProductOption]
