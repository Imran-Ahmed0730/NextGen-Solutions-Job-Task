from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.product_categories.models import ProductCategory


def list_categories(
    db: Session, *, include_inactive: bool, offset: int, limit: int
) -> list[ProductCategory]:
    statement = select(ProductCategory)
    if not include_inactive:
        statement = statement.where(
            ProductCategory.is_active.is_(True), ProductCategory.deleted_at.is_(None)
        )
    return list(
        db.scalars(
            statement.order_by(ProductCategory.name, ProductCategory.id).offset(offset).limit(limit)
        )
    )


def get_category(db: Session, category_id: int) -> ProductCategory | None:
    return db.get(ProductCategory, category_id)
