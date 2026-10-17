from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.incomes import service
from app.modules.incomes.models import Income
from app.modules.incomes.schemas import (
    IncomeCreate,
    IncomeOptionsResponse,
    IncomeResponse,
)

router = APIRouter(prefix="/api/v1/incomes", tags=["incomes"])


@router.get("/options", response_model=IncomeOptionsResponse)
def get_income_options(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("money.incomes.read")),
) -> IncomeOptionsResponse:
    return service.get_income_options(db)


@router.get("", response_model=list[IncomeResponse])
def list_incomes(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("money.incomes.read")),
) -> list[Income]:
    return service.list_incomes(db, offset=offset, limit=limit)


@router.post("", response_model=IncomeResponse, status_code=status.HTTP_201_CREATED)
def create_income(
    payload: IncomeCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("money.incomes.create")),
) -> Income:
    ip = request.client.host if request.client else None
    return service.create_income(db, payload, actor, ip)


@router.get("/{income_id}", response_model=IncomeResponse)
def get_income(
    income_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("money.incomes.read")),
) -> Income:
    income = service.get_income(db, income_id)
    if income is None:
        raise HTTPException(status_code=404, detail="Income not found")
    return income
