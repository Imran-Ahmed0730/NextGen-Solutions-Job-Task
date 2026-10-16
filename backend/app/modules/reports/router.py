from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.reports import service
from app.modules.reports.schemas import (
    DashboardResponse,
    ReportOptionsResponse,
    ReportResponse,
    ReportType,
)

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    period_from: date | None = Query(default=None),
    period_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("reports.dashboard.read")),
) -> dict[str, object]:
    return service.get_dashboard(db, period_from=period_from, period_to=period_to)


@router.get("", response_model=ReportResponse)
def get_report(
    report_type: ReportType = Query(),
    period_from: date | None = Query(default=None),
    period_to: date | None = Query(default=None),
    warehouse_id: int | None = Query(default=None, ge=1),
    party_id: int | None = Query(default=None, ge=1),
    product_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("reports.read")),
) -> dict[str, object]:
    return service.get_report(
        db,
        report_type=report_type,
        period_from=period_from,
        period_to=period_to,
        warehouse_id=warehouse_id,
        party_id=party_id,
        product_id=product_id,
    )


@router.get("/options", response_model=ReportOptionsResponse)
def get_report_options(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("reports.read")),
) -> dict[str, list[dict[str, object]]]:
    return service.get_report_options(db)
