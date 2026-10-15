from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.interfaces import ORMOption

from app.modules.sales.models import SalesDelivery, SalesOrder, SalesOrderLine


def _sales_order_options() -> tuple[ORMOption, ORMOption]:
    return (
        selectinload(SalesOrder.lines).selectinload(SalesOrderLine.reservations),
        selectinload(SalesOrder.deliveries).selectinload(SalesDelivery.lines),
    )


def list_sales_orders(db: Session, *, offset: int = 0, limit: int = 50) -> list[SalesOrder]:
    statement = (
        select(SalesOrder)
        .options(*_sales_order_options())
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
        .options(*_sales_order_options())
        .where(SalesOrder.id == sales_order_id)
    )
    if for_update:
        statement = statement.with_for_update()
    return db.scalar(statement)
