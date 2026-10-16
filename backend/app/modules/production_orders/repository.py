from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.modules.production_orders.models import ProductionOrder


def list_production_orders(
    db: Session, *, offset: int, limit: int
) -> list[ProductionOrder]:
    statement = (
        select(ProductionOrder)
        .options(
            selectinload(ProductionOrder.consumption),
            selectinload(ProductionOrder.outputs),
        )
        .order_by(ProductionOrder.doc_date.desc(), ProductionOrder.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(statement))


def get_production_order(
    db: Session, production_order_id: int, *, for_update: bool = False
) -> ProductionOrder | None:
    statement = (
        select(ProductionOrder)
        .options(
            selectinload(ProductionOrder.consumption),
            selectinload(ProductionOrder.outputs),
        )
        .where(ProductionOrder.id == production_order_id)
    )
    if for_update:
        statement = statement.with_for_update()
    return db.scalar(statement)
