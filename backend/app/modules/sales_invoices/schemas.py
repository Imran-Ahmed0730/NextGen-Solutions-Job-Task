from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SalesInvoiceCreate(BaseModel):
    delivery_id: int = Field(ge=1)
    doc_date: date
    due_date: date


class SalesInvoiceLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    qty: Decimal
    unit_price: Decimal
    line_total: Decimal
    unit_cost_cogs: Decimal


class SalesInvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doc_no: str
    doc_date: date
    due_date: date
    customer_id: int
    delivery_id: int
    status: str
    subtotal: Decimal
    discount: Decimal
    total: Decimal
    cogs_total: Decimal
    lines: list[SalesInvoiceLineResponse]


class SalesInvoiceCreateResponse(BaseModel):
    invoice: SalesInvoiceResponse
    credit_limit_warning: bool


class SalesInvoicePrintCompany(BaseModel):
    company_name: str
    company_logo_path: str
    address: str
    phone: str
    email: str
    currency_code: str | None
    footer: str


class SalesInvoicePrintCustomer(BaseModel):
    code: str
    name: str
    mobile: str | None
    email: str | None
    address: str | None


class SalesInvoicePrintLine(BaseModel):
    product_sku: str
    product_name: str
    unit_code: str
    qty: Decimal
    unit_price: Decimal
    line_total: Decimal


class SalesInvoicePrintResponse(BaseModel):
    company: SalesInvoicePrintCompany
    invoice_no: str
    invoice_date: date
    due_date: date
    delivery_no: str
    order_no: str
    customer: SalesInvoicePrintCustomer
    lines: list[SalesInvoicePrintLine]
    subtotal: Decimal
    discount: Decimal
    total: Decimal


class SalesInvoiceDeliveryOption(BaseModel):
    id: int
    doc_no: str
    doc_date: date
    order_doc_no: str


class SalesInvoiceOptionsResponse(BaseModel):
    deliveries: list[SalesInvoiceDeliveryOption]
