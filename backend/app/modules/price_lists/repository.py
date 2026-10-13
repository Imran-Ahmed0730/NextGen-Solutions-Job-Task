from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.price_lists.models import PriceList, ProductPrice


def list_price_lists(
    db: Session, *, include_inactive: bool = False, offset: int = 0, limit: int = 50
) -> list[PriceList]:
    statement = select(PriceList)
    if not include_inactive:
        statement = statement.where(
            PriceList.is_active.is_(True), PriceList.deleted_at.is_(None)
        )
    return list(
        db.scalars(
            statement.order_by(PriceList.name, PriceList.id).offset(offset).limit(limit)
        )
    )


def get_price_list(db: Session, price_list_id: int) -> PriceList | None:
    return db.get(PriceList, price_list_id)


def list_default_price_lists(
    db: Session, *, exclude_id: int | None = None
) -> list[PriceList]:
    statement = select(PriceList).where(
        PriceList.is_default.is_(True), PriceList.deleted_at.is_(None)
    )
    if exclude_id is not None:
        statement = statement.where(PriceList.id != exclude_id)
    return list(db.scalars(statement))


def list_product_prices(db: Session, price_list_id: int) -> list[ProductPrice]:
    statement = (
        select(ProductPrice)
        .where(ProductPrice.price_list_id == price_list_id)
        .order_by(ProductPrice.product_id, ProductPrice.id)
    )
    return list(db.scalars(statement))


def get_product_price(db: Session, product_price_id: int) -> ProductPrice | None:
    return db.get(ProductPrice, product_price_id)


def get_product_price_by_list_and_product(
    db: Session, price_list_id: int, product_id: int
) -> ProductPrice | None:
    statement = select(ProductPrice).where(
        ProductPrice.price_list_id == price_list_id,
        ProductPrice.product_id == product_id,
    )
    return db.scalar(statement)