from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.payroll import service
from app.modules.payroll.models import PayrollRun
from app.modules.payroll.schemas import (
    PayrollLineUpdate,
    PayrollOptionsResponse,
    PayrollPost,
    PayrollRunCreate,
    PayrollRunResponse,
)

router = APIRouter(prefix="/api/v1/payroll", tags=["payroll"])


@router.get("/options", response_model=PayrollOptionsResponse)
def get_payroll_options(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("employees.payroll.read")),
) -> PayrollOptionsResponse:
    return service.get_options(db)


@router.get("/runs", response_model=list[PayrollRunResponse])
def list_payroll_runs(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("employees.payroll.read")),
) -> list[PayrollRun]:
    return service.list_runs(db, offset=offset, limit=limit)


@router.post(
    "/runs",
    response_model=PayrollRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_payroll_run(
    payload: PayrollRunCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("employees.payroll.create")),
) -> PayrollRun:
    return service.create_run(db, payload, actor, _ip(request))


@router.get("/runs/{run_id}", response_model=PayrollRunResponse)
def get_payroll_run(
    run_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("employees.payroll.read")),
) -> PayrollRun:
    return service.get_run(db, run_id)


@router.patch("/runs/{run_id}/lines/{line_id}", response_model=PayrollRunResponse)
def update_payroll_line(
    run_id: int,
    line_id: int,
    payload: PayrollLineUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("employees.payroll.update")),
) -> PayrollRun:
    return service.update_line(
        db, run_id, line_id, payload.deductions, actor, _ip(request)
    )


@router.post("/runs/{run_id}/post", response_model=PayrollRunResponse)
def post_payroll_run(
    run_id: int,
    payload: PayrollPost,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("employees.payroll.post")),
) -> PayrollRun:
    return service.post_run(
        db,
        run_id,
        account_id=payload.account_id,
        paid_on=payload.paid_on,
        actor=actor,
        ip=_ip(request),
    )


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None
