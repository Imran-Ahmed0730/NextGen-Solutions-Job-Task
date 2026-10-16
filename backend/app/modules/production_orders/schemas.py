from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Quantity = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=3)]
Cost = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)]


class ProductionOrderCreate(BaseModel):
    doc_date: date
    bom_id: int = Field(gt=0)
    planned_qty: Quantity
    warehouse_id: int = Field(gt=0)


class ProductionOrderComplete(BaseModel):
    actual_qty: Quantity
    labor_cost: Cost
    overhead_cost: Cost


class ProductionConsumptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    qty: Decimal
    unit_cost: Decimal
    line_cost: Decimal


class ProductionOutputResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    qty: Decimal
    unit_cost: Decimal


class ProductionOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doc_no: str
    doc_date: date
    bom_id: int
    finished_product_id: int
    planned_qty: Decimal
    actual_qty: Decimal | None
    warehouse_id: int
    status: str
    labor_cost: Decimal | None
    overhead_cost: Decimal | None
    material_cost: Decimal | None
    total_cost: Decimal | None
    unit_cost: Decimal | None
    created_by: int | None
    created_at: datetime
    updated_at: datetime
    consumption: list[ProductionConsumptionResponse]
    outputs: list[ProductionOutputResponse]


class ProductionOrderBOMOption(BaseModel):
    id: int
    code: str
    finished_product_id: int
    output_qty: Decimal
    labor_cost_default: Decimal
    overhead_cost_default: Decimal


class ProductionOrderWarehouseOption(BaseModel):
    id: int
    code: str
    name: str


class ProductionOrderOptionsResponse(BaseModel):
    boms: list[ProductionOrderBOMOption]
    warehouses: list[ProductionOrderWarehouseOption]
