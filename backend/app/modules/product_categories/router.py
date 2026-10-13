from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.product_categories import service
from app.modules.product_categories.models import ProductCategory
from app.modules.product_categories.repository import get_category
from app.modules.product_categories.schemas import (
    ProductCategoryCreate,
    ProductCategoryResponse,
    ProductCategoryUpdate,
)

router = APIRouter(prefix="/api/v1/product-categories", tags=["product-categories"])


def _category_or_404(db: Session, category_id: int) -> ProductCategory:
    category = get_category(db, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Product category not found")
    return category


@router.get("", response_model=list[ProductCategoryResponse])
def list_categories(
    include_inactive: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master_data.product_categories.read")),
) -> list[ProductCategory]:
    return service.list_categories(
        db, include_inactive=include_inactive, offset=offset, limit=limit
    )


@router.post("", response_model=ProductCategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: ProductCategoryCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.product_categories.create")),
) -> ProductCategory:
    return service.create_category(db, payload.model_dump(), actor, _ip(request))


@router.patch("/{category_id}", response_model=ProductCategoryResponse)
def update_category(
    category_id: int,
    payload: ProductCategoryUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.product_categories.update")),
) -> ProductCategory:
    return service.update_category(
        db,
        _category_or_404(db, category_id),
        payload.model_dump(exclude_unset=True),
        actor,
        _ip(request),
    )


@router.delete("/{category_id}", response_model=ProductCategoryResponse)
def delete_category(
    category_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.product_categories.delete")),
) -> ProductCategory:
    return service.delete_category(db, _category_or_404(db, category_id), actor, _ip(request))


@router.post("/{category_id}/activate", response_model=ProductCategoryResponse)
def activate_category(
    category_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.product_categories.update")),
) -> ProductCategory:
    return service.activate_category(db, _category_or_404(db, category_id), actor, _ip(request))


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None
