from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.modules.purchase_orders.models import PurchaseOrder


def list_purchase_orders(db: Session, *, offset: int = 0, limit: int = 50) -> list[PurchaseOrder]:
    statement = (
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.lines))
        .order_by(PurchaseOrder.doc_date.desc(), PurchaseOrder.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(statement))


def get_purchase_order(
    db: Session, purchase_order_id: int, *, for_update: bool = False
) -> PurchaseOrder | None:
    statement = (
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.lines))
        .where(PurchaseOrder.id == purchase_order_id)
    )
    if for_update:
        statement = statement.with_for_update()
    return db.scalar(statement)
