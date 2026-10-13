from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.products import service
from app.modules.products.models import Product, ProductType
from app.modules.products.schemas import ProductCreate, ProductResponse, ProductUpdate

router = APIRouter(prefix="/api/v1/products", tags=["products"])


def _product_or_404(db: Session, product_id: int) -> Product:
    product = service.get_product(db, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


def _serialize(product: Product) -> ProductResponse:
    return ProductResponse(
        id=product.id,
        sku=product.sku,
        name=product.name,
        type=product.type,
        category_id=product.category_id,
        category_name=product.category.name if product.category else None,
        unit_id=product.unit_id,
        unit_name=product.unit.name if product.unit else None,
        unit_code=product.unit.code if product.unit else None,
        is_stocked=product.is_stocked,
        reorder_level=product.reorder_level,
        avg_cost=product.avg_cost,
        sales_price_default=product.sales_price_default,
        description=product.description,
        is_active=product.is_active,
        deleted_at=product.deleted_at,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


@router.get("", response_model=list[ProductResponse])
def list_products(
    search: str | None = None,
    category_id: int | None = None,
    product_type: ProductType | None = None,
    include_inactive: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master_data.products.read")),
) -> list[ProductResponse]:
    products = service.list_products(
        db,
        search=search,
        category_id=category_id,
        product_type=product_type,
        include_inactive=include_inactive,
        offset=offset,
        limit=limit,
    )
    return [_serialize(p) for p in products]


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.products.create")),
) -> ProductResponse:
    product = service.create_product(db, payload.model_dump(), actor, _ip(request))
    return _serialize(product)


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master_data.products.read")),
) -> ProductResponse:
    product = _product_or_404(db, product_id)
    return _serialize(product)


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.products.update")),
) -> ProductResponse:
    product = _product_or_404(db, product_id)
    updated = service.update_product(
        db, product, payload.model_dump(exclude_unset=True), actor, _ip(request)
    )
    return _serialize(updated)


@router.delete("/{product_id}", response_model=ProductResponse)
def delete_product(
    product_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.products.delete")),
) -> ProductResponse:
    product = _product_or_404(db, product_id)
    deleted = service.delete_product(db, product, actor, _ip(request))
    return _serialize(deleted)


@router.post("/{product_id}/activate", response_model=ProductResponse)
def activate_product(
    product_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.products.update")),
) -> ProductResponse:
    product = _product_or_404(db, product_id)
    activated = service.activate_product(db, product, actor, _ip(request))
    return _serialize(activated)


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None
