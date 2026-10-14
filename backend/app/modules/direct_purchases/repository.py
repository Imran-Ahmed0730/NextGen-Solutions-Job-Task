from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.modules.direct_purchases.models import DirectPurchase


def list_direct_purchases(db: Session, *, offset: int = 0, limit: int = 50) -> list[DirectPurchase]:
    statement = (
        select(DirectPurchase)
        .options(selectinload(DirectPurchase.lines))
        .order_by(DirectPurchase.doc_date.desc(), DirectPurchase.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(statement))


def get_direct_purchase(db: Session, purchase_id: int) -> DirectPurchase | None:
    statement = (
        select(DirectPurchase)
        .options(selectinload(DirectPurchase.lines))
        .where(DirectPurchase.id == purchase_id)
    )
    return db.scalar(statement)


def list_supplier_due_entries(db: Session, supplier_id: int) -> list[DirectPurchase]:
    statement = (
        select(DirectPurchase)
        .where(DirectPurchase.supplier_id == supplier_id, DirectPurchase.status == "POSTED")
        .order_by(DirectPurchase.doc_date, DirectPurchase.id)
    )
    return list(db.scalars(statement))
