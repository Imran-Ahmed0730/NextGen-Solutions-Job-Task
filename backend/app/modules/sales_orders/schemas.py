from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

SalesOrderNote = Annotated[str, StringConstraints(max_length=2000)]


class SalesOrderReservationInput(BaseModel):
    qty: Decimal = Field(gt=0, max_digits=18, decimal_places=3, allow_inf_nan=False)


class SalesOrderReservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    qty: Decimal
    qty_consumed: Decimal
    qty_released: Decimal
    status: str


class SalesOrderDeliveryLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_line_id: int
    product_id: int
    qty: Decimal
    unit_cost_cogs: Decimal


class SalesOrderDeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doc_no: str
    doc_date: date
    status: str
    lines: list[SalesOrderDeliveryLineResponse]


class SalesDeliveryLineInput(BaseModel):
    order_line_id: int = Field(ge=1)
    qty: Decimal = Field(gt=0, max_digits=18, decimal_places=3, allow_inf_nan=False)


class SalesDeliveryCreate(BaseModel):
    doc_date: date
    lines: list[SalesDeliveryLineInput] = Field(min_length=1, max_length=500)


class SalesDeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doc_no: str
    doc_date: date
    order_id: int
    customer_id: int
    warehouse_id: int
    status: str
    lines: list[SalesOrderDeliveryLineResponse]


class SalesOrderLineInput(BaseModel):
    product_id: int = Field(ge=1)
    qty_ordered: Decimal = Field(gt=0, max_digits=18, decimal_places=3, allow_inf_nan=False)
    unit_price: Decimal = Field(ge=0, max_digits=18, decimal_places=2, allow_inf_nan=False)


class SalesOrderCreate(BaseModel):
    doc_date: date
    customer_id: int = Field(ge=1)
    warehouse_id: int = Field(ge=1)
    delivery_date: date | None = None
    discount: Decimal = Field(
        default=Decimal("0.00"), ge=0, max_digits=18, decimal_places=2, allow_inf_nan=False
    )
    note: SalesOrderNote | None = None
    lines: list[SalesOrderLineInput] = Field(min_length=1, max_length=500)


class SalesOrderUpdate(SalesOrderCreate):
    pass


class SalesOrderLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    qty_ordered: Decimal
    unit_price: Decimal
    line_total: Decimal
    qty_reserved: Decimal
    qty_produced: Decimal
    qty_delivered: Decimal
    qty_available: Decimal = Decimal("0.000")
    qty_remaining: Decimal = Decimal("0.000")
    reservations: list[SalesOrderReservationResponse]


class SalesOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doc_no: str
    doc_date: date
    customer_id: int
    quotation_id: int | None
    warehouse_id: int
    status: str
    delivery_date: date | None
    subtotal: Decimal
    discount: Decimal
    total: Decimal
    note: str | None
    lines: list[SalesOrderLineResponse]
    deliveries: list[SalesOrderDeliveryResponse]


class SalesOrderCustomerOption(BaseModel):
    id: int
    code: str
    name: str


class SalesOrderWarehouseOption(BaseModel):
    id: int
    code: str
    name: str


class SalesOrderProductOption(BaseModel):
    id: int
    sku: str
    name: str
    unit_code: str
    allow_decimal: bool


class SalesOrderOptionsResponse(BaseModel):
    customers: list[SalesOrderCustomerOption]
    warehouses: list[SalesOrderWarehouseOption]
    products: list[SalesOrderProductOption]
