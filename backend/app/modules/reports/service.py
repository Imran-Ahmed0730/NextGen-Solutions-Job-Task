from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.reports import repository
from app.modules.reports.schemas import ReportType


def get_dashboard(
    db: Session,
    *,
    period_from: date | None = None,
    period_to: date | None = None,
) -> dict[str, object]:
    end = period_to or date.today()
    start = period_from or end
    if start > end:
        raise HTTPException(status_code=422, detail="Start date cannot be after end date.")
    if end - start > timedelta(days=3660):
        raise HTTPException(status_code=422, detail="Dashboard date range cannot exceed 10 years.")
    return repository.dashboard_totals(db, start, end)


REPORT_COLUMNS: dict[ReportType, list[str]] = {
    "sales": ["date", "document", "party", "type", "amount", "cogs"],
    "purchases": ["date", "document", "party", "type", "amount"],
    "stock_valuation": ["sku", "product", "on_hand", "reorder_level", "unit_cost", "value"],
    "low_stock": ["sku", "product", "on_hand", "reorder_level", "unit_cost", "value"],
    "customer_due": ["code", "party", "due"],
    "supplier_due": ["code", "party", "due"],
    "production_cost": [
        "date",
        "document",
        "status",
        "output_qty",
        "material_cost",
        "labor_cost",
        "overhead_cost",
        "total_cost",
        "unit_cost",
    ],
    "cash_book": ["date", "account", "type", "source", "source_id", "amount", "note"],
    "expense_income": ["date", "document", "type", "amount"],
    "profit": ["sales", "cogs", "expenses", "estimated_profit"],
    "assets": [
        "asset_code",
        "asset",
        "category",
        "purchase_date",
        "purchase_cost",
        "location",
        "status",
    ],
    "attendance_payroll": [
        "date",
        "status",
        "employee_count",
        "year",
        "month",
        "document",
        "total_amount",
    ],
}


def get_report(
    db: Session,
    *,
    report_type: ReportType,
    period_from: date | None = None,
    period_to: date | None = None,
    warehouse_id: int | None = None,
    party_id: int | None = None,
    product_id: int | None = None,
) -> dict[str, object]:
    end = period_to or date.today()
    start = period_from or end
    if start > end:
        raise HTTPException(status_code=422, detail="Start date cannot be after end date.")
    if end - start > timedelta(days=3660):
        raise HTTPException(status_code=422, detail="Report date range cannot exceed 10 years.")
    if warehouse_id is not None and report_type not in {
        "stock_valuation",
        "low_stock",
        "production_cost",
    }:
        raise HTTPException(
            status_code=422,
            detail="Warehouse filter is only valid for stock reports.",
        )
    if party_id is not None and report_type not in {
        "sales",
        "purchases",
        "customer_due",
        "supplier_due",
    }:
        raise HTTPException(status_code=422, detail="Party filter is not valid for this report.")
    if product_id is not None and report_type not in {
        "sales",
        "purchases",
        "stock_valuation",
        "low_stock",
        "production_cost",
    }:
        raise HTTPException(status_code=422, detail="Product filter is not valid for this report.")

    return {
        "report_type": report_type,
        "title": repository.REPORT_TITLES[report_type],
        "period_from": start,
        "period_to": end,
        "columns": REPORT_COLUMNS[report_type],
        "rows": repository.report_data(
            db,
            report_type,
            start,
            end,
            warehouse_id,
            party_id,
            product_id,
        ),
    }


def get_report_options(db: Session) -> dict[str, list[dict[str, object]]]:
    return repository.report_options(db)
