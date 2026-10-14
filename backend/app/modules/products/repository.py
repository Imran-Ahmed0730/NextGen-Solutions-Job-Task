from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, lazyload

from app.modules.products.models import Product, ProductType


def list_products(
    db: Session,
    *,
    search: str | None = None,
    category_id: int | None = None,
    product_type: ProductType | None = None,
    include_inactive: bool = False,
    offset: int = 0,
    limit: int = 50,
) -> list[Product]:
    statement = select(Product).options(joinedload(Product.category), joinedload(Product.unit))
    if not include_inactive:
        statement = statement.where(Product.is_active.is_(True), Product.deleted_at.is_(None))
    if category_id is not None:
        statement = statement.where(Product.category_id == category_id)
    if product_type is not None:
        statement = statement.where(Product.type == product_type)
    if search:
        search_term = f"%{search.strip().lower()}%"
        statement = statement.where(
            or_(
                func.lower(Product.name).like(search_term),
                func.lower(Product.sku).like(search_term),
            )
        )
    return list(
        db.scalars(statement.order_by(Product.name, Product.id).offset(offset).limit(limit))
    )


def get_product(db: Session, product_id: int) -> Product | None:
    statement = (
        select(Product)
        .options(joinedload(Product.category), joinedload(Product.unit))
        .where(Product.id == product_id)
    )
    return db.scalar(statement)


def lock_product_for_stock_posting(db: Session, product_id: int) -> Product | None:
    statement = (
        select(Product)
        .options(lazyload(Product.category), lazyload(Product.unit))
        .where(Product.id == product_id)
        .with_for_update()
    )
    return db.scalar(statement)


def get_product_by_sku(db: Session, sku: str, *, exclude_id: int | None = None) -> Product | None:
    statement = select(Product).where(func.lower(Product.sku) == sku.lower())
    if exclude_id is not None:
        statement = statement.where(Product.id != exclude_id)
    return db.scalar(statement)
