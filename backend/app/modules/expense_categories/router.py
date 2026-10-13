from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.expense_categories import service
from app.modules.expense_categories.models import ExpenseCategory
from app.modules.expense_categories.schemas import (
    ExpenseCategoryCreate,
    ExpenseCategoryResponse,
    ExpenseCategoryUpdate,
)

router = APIRouter(prefix="/api/v1/expense-categories", tags=["expense-categories"])


def _category_or_404(db: Session, category_id: int) -> ExpenseCategory:
    category = service.get_category(db, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Expense category not found")
    return category


@router.get("", response_model=list[ExpenseCategoryResponse])
def list_categories(
    include_inactive: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master_data.expense_categories.read")),
) -> list[ExpenseCategory]:
    return service.list_categories(
        db, include_inactive=include_inactive, offset=offset, limit=limit
    )


@router.post("", response_model=ExpenseCategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: ExpenseCategoryCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.expense_categories.create")),
) -> ExpenseCategory:
    return service.create_category(db, payload.model_dump(), actor, _ip(request))


@router.get("/{category_id}", response_model=ExpenseCategoryResponse)
def get_category(
    category_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master_data.expense_categories.read")),
) -> ExpenseCategory:
    return _category_or_404(db, category_id)


@router.patch("/{category_id}", response_model=ExpenseCategoryResponse)
def update_category(
    category_id: int,
    payload: ExpenseCategoryUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.expense_categories.update")),
) -> ExpenseCategory:
    category = _category_or_404(db, category_id)
    return service.update_category(
        db, category, payload.model_dump(exclude_unset=True), actor, _ip(request)
    )


@router.delete("/{category_id}", response_model=ExpenseCategoryResponse)
def delete_category(
    category_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.expense_categories.delete")),
) -> ExpenseCategory:
    return service.delete_category(db, _category_or_404(db, category_id), actor, _ip(request))


@router.post("/{category_id}/activate", response_model=ExpenseCategoryResponse)
def activate_category(
    category_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.expense_categories.update")),
) -> ExpenseCategory:
    return service.activate_category(
        db, _category_or_404(db, category_id), actor, _ip(request)
    )


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None