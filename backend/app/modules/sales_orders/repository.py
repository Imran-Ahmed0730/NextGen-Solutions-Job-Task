from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.modules.sales.models import SalesOrder


def list_sales_orders(db: Session, *, offset: int = 0, limit: int = 50) -> list[SalesOrder]:
    statement = (
        select(SalesOrder)
        .options(selectinload(SalesOrder.lines))
        .order_by(SalesOrder.doc_date.desc(), SalesOrder.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(statement))


def get_sales_order(
    db: Session, sales_order_id: int, *, for_update: bool = False
) -> SalesOrder | None:
    statement = (
        select(SalesOrder)
        .options(selectinload(SalesOrder.lines))
        .where(SalesOrder.id == sales_order_id)
    )
    if for_update:
        statement = statement.with_for_update()
    return db.scalar(statement)
