from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.expenses import service
from app.modules.expenses.models import Expense
from app.modules.expenses.schemas import (
    ExpenseCreate,
    ExpenseOptionsResponse,
    ExpenseResponse,
)

router = APIRouter(prefix="/api/v1/expenses", tags=["expenses"])


@router.get("/options", response_model=ExpenseOptionsResponse)
def get_expense_options(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("money.expenses.read")),
) -> ExpenseOptionsResponse:
    return service.get_expense_options(db)


@router.get("", response_model=list[ExpenseResponse])
def list_expenses(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("money.expenses.read")),
) -> list[Expense]:
    return service.list_expenses(db, offset=offset, limit=limit)


@router.post("", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
def create_expense(
    payload: ExpenseCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("money.expenses.create")),
) -> Expense:
    ip = request.client.host if request.client else None
    return service.create_expense(db, payload, actor, ip)


@router.get("/{expense_id}", response_model=ExpenseResponse)
def get_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("money.expenses.read")),
) -> Expense:
    expense = service.get_expense(db, expense_id)
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense


@router.put("/{expense_id}", response_model=ExpenseResponse)
def update_rejected_expense(
    expense_id: int,
    payload: ExpenseCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("money.expenses.update")),
) -> Expense:
    ip = request.client.host if request.client else None
    return service.update_rejected_expense(db, expense_id, payload, actor, ip)
