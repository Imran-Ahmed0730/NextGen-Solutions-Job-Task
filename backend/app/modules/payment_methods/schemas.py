from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.modules.payment_methods.models import PaymentMethodType

PaymentMethodName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]


class PaymentMethodCreate(BaseModel):
    name: PaymentMethodName
    type: PaymentMethodType
    is_active: bool = True


class PaymentMethodUpdate(BaseModel):
    name: PaymentMethodName | None = None
    type: PaymentMethodType | None = None
    is_active: bool | None = None


class PaymentMethodResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: PaymentMethodType
    is_active: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime