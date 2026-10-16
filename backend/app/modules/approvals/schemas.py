from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

DocumentType = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_upper=True,
        min_length=1,
        max_length=50,
        pattern=r"^[A-Z][A-Z0-9_]*$",
    ),
]
Threshold = Annotated[
    Decimal, Field(ge=0, max_digits=18, decimal_places=2, allow_inf_nan=False)
]
PositiveRoleId = Annotated[int, Field(gt=0)]


class ApprovalRuleCreate(BaseModel):
    doc_type: DocumentType
    min_amount: Threshold
    max_amount: Threshold | None = None
    approver_role_id: PositiveRoleId

    @field_validator("doc_type", mode="before")
    @classmethod
    def normalize_document_type(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_range(self) -> "ApprovalRuleCreate":
        if self.max_amount is not None and self.max_amount < self.min_amount:
            raise ValueError("Maximum amount must be at least the minimum amount")
        return self


class ApprovalRuleUpdate(BaseModel):
    doc_type: DocumentType | None = None
    min_amount: Threshold | None = None
    max_amount: Threshold | None = None
    approver_role_id: PositiveRoleId | None = None

    @field_validator("doc_type", mode="before")
    @classmethod
    def normalize_document_type(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_range(self) -> "ApprovalRuleUpdate":
        if (
            self.min_amount is not None
            and self.max_amount is not None
            and self.max_amount < self.min_amount
        ):
            raise ValueError("Maximum amount must be at least the minimum amount")
        return self


class ApprovalRoleResponse(BaseModel):
    id: int
    name: str


class ApprovalRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doc_type: str
    min_amount: Decimal
    max_amount: Decimal | None
    approver_role_id: int
    approver_role: ApprovalRoleResponse
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ApprovalRoleOption(BaseModel):
    id: int
    name: str
