from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.income_categories import service
from app.modules.income_categories.models import IncomeCategory
from app.modules.income_categories.schemas import (
    IncomeCategoryCreate,
    IncomeCategoryResponse,
    IncomeCategoryUpdate,
)

router = APIRouter(prefix="/api/v1/income-categories", tags=["income-categories"])


def _category_or_404(db: Session, category_id: int) -> IncomeCategory:
    category = service.get_category(db, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Income category not found")
    return category


@router.get("", response_model=list[IncomeCategoryResponse])
def list_categories(
    include_inactive: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master_data.income_categories.read")),
) -> list[IncomeCategory]:
    return service.list_categories(
        db, include_inactive=include_inactive, offset=offset, limit=limit
    )


@router.post("", response_model=IncomeCategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: IncomeCategoryCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.income_categories.create")),
) -> IncomeCategory:
    return service.create_category(db, payload.model_dump(), actor, _ip(request))


@router.get("/{category_id}", response_model=IncomeCategoryResponse)
def get_category(
    category_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master_data.income_categories.read")),
) -> IncomeCategory:
    return _category_or_404(db, category_id)


@router.patch("/{category_id}", response_model=IncomeCategoryResponse)
def update_category(
    category_id: int,
    payload: IncomeCategoryUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.income_categories.update")),
) -> IncomeCategory:
    category = _category_or_404(db, category_id)
    return service.update_category(
        db, category, payload.model_dump(exclude_unset=True), actor, _ip(request)
    )


@router.delete("/{category_id}", response_model=IncomeCategoryResponse)
def delete_category(
    category_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.income_categories.delete")),
) -> IncomeCategory:
    return service.delete_category(db, _category_or_404(db, category_id), actor, _ip(request))


@router.post("/{category_id}/activate", response_model=IncomeCategoryResponse)
def activate_category(
    category_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.income_categories.update")),
) -> IncomeCategory:
    return service.activate_category(db, _category_or_404(db, category_id), actor, _ip(request))


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None
