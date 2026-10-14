from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PhysicalCountCreate(BaseModel):
    count_date: date
    warehouse_id: int = Field(ge=1)


class PhysicalCountLineCounted(BaseModel):
    product_id: int = Field(ge=1)
    counted_qty: Decimal = Field(max_digits=18, decimal_places=3, allow_inf_nan=False)


class PhysicalCountLinesUpdate(BaseModel):
    lines: list[PhysicalCountLineCounted] = Field(min_length=1)


class PhysicalCountLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    product_sku: str
    product_name: str
    unit_code: str
    system_qty: Decimal
    counted_qty: Decimal | None
    variance_qty: Decimal | None


class PhysicalCountResponse(BaseModel):
    id: int
    doc_no: str | None
    count_date: date
    warehouse_id: int
    status: str
    created_by: int | None
    posted_by: int | None
    posted_at: datetime | None
    lines: list[PhysicalCountLineResponse]


class PhysicalCountListItem(BaseModel):
    id: int
    doc_no: str | None
    count_date: date
    warehouse_id: int
    status: str
    total_lines: int
    counted_lines: int


class PhysicalCountWarehouseOption(BaseModel):
    id: int
    code: str
    name: str
