from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

ReportType = Literal[
    "sales",
    "purchases",
    "stock_valuation",
    "low_stock",
    "customer_due",
    "supplier_due",
    "production_cost",
    "cash_book",
    "expense_income",
    "profit",
    "assets",
    "attendance_payroll",
]


class DashboardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    period_from: date
    period_to: date
    sales: Decimal
    collections: Decimal
    expenses: Decimal
    purchases: Decimal
    account_balances: dict[str, Decimal]
    customer_due: Decimal
    supplier_due: Decimal
    inventory_value: Decimal
    pending_orders: int
    estimated_profit: Decimal


class ReportResponse(BaseModel):
    report_type: ReportType
    title: str
    period_from: date
    period_to: date
    columns: list[str]
    rows: list[dict[str, object]]


class ReportOption(BaseModel):
    id: int
    label: str


class ReportOptionsResponse(BaseModel):
    customers: list[ReportOption]
    suppliers: list[ReportOption]
    products: list[ReportOption]
    warehouses: list[ReportOption]
