from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, lazyload, selectinload

from app.modules.purchase_returns.models import PurchaseReturn, PurchaseReturnLine


def list_purchase_returns(db: Session, *, offset: int = 0, limit: int = 50) -> list[PurchaseReturn]:
    statement = (
        select(PurchaseReturn)
        .options(selectinload(PurchaseReturn.lines))
        .order_by(PurchaseReturn.doc_date.desc(), PurchaseReturn.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(statement))


def get_purchase_return(db: Session, return_id: int) -> PurchaseReturn | None:
    statement = (
        select(PurchaseReturn)
        .options(selectinload(PurchaseReturn.lines))
        .where(PurchaseReturn.id == return_id)
    )
    return db.scalar(statement)


def list_existing_return_lines_for_update(db: Session, receipt_id: int) -> list[PurchaseReturnLine]:
    statement = (
        select(PurchaseReturnLine)
        .options(lazyload(PurchaseReturnLine.product))
        .join(PurchaseReturn, PurchaseReturn.id == PurchaseReturnLine.return_id)
        .where(PurchaseReturn.receipt_id == receipt_id)
        .order_by(PurchaseReturnLine.id)
        .with_for_update()
    )
    return list(db.scalars(statement))


def get_returned_quantities(db: Session, receipt_ids: Sequence[int]) -> dict[int, Decimal]:
    if not receipt_ids:
        return {}

    statement = (
        select(PurchaseReturnLine.receipt_line_id, func.sum(PurchaseReturnLine.qty))
        .join(PurchaseReturn, PurchaseReturn.id == PurchaseReturnLine.return_id)
        .where(PurchaseReturn.receipt_id.in_(receipt_ids), PurchaseReturn.status == "POSTED")
        .group_by(PurchaseReturnLine.receipt_line_id)
    )
    return {line_id: qty for line_id, qty in db.execute(statement)}


def list_supplier_due_entries(db: Session, supplier_id: int) -> list[PurchaseReturn]:
    statement = (
        select(PurchaseReturn)
        .where(PurchaseReturn.supplier_id == supplier_id, PurchaseReturn.status == "POSTED")
        .order_by(PurchaseReturn.doc_date, PurchaseReturn.id)
    )
    return list(db.scalars(statement))
