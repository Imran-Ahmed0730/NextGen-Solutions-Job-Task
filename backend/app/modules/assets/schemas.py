from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

AssetCode = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
AssetName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
AssetCategory = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
AssetLocation = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)
]
AssetStatus = Literal["IN_USE", "IN_STORE", "UNDER_MAINTENANCE", "DISPOSED"]
Money = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)]


class AssetCreate(BaseModel):
    asset_code: AssetCode
    name: AssetName
    category: AssetCategory
    purchase_date: date
    purchase_cost: Money
    location: AssetLocation
    status: AssetStatus = "IN_STORE"


class AssetUpdate(BaseModel):
    asset_code: AssetCode | None = None
    name: AssetName | None = None
    category: AssetCategory | None = None
    purchase_date: date | None = None
    purchase_cost: Money | None = None
    location: AssetLocation | None = None
    status: AssetStatus | None = None


class AssetAssignmentCreate(BaseModel):
    location: AssetLocation
    assigned_on: date


class AssetAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: int
    location: str
    assigned_on: date
    returned_on: date | None


class AssetMaintenanceCreate(BaseModel):
    maintenance_date: date
    description: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
    ]
    cost: Money
    next_due_date: date | None = None


class AssetMaintenanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: int
    maintenance_date: date
    description: str
    cost: Decimal
    next_due_date: date | None


class AssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_code: str
    name: str
    category: str
    purchase_date: date
    purchase_cost: Decimal
    location: str
    status: str
    is_active: bool
    deleted_at: datetime | None
    assignments: list[AssetAssignmentResponse]
    maintenance: list[AssetMaintenanceResponse]
