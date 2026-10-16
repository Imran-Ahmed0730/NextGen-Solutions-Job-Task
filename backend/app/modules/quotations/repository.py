from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.modules.quotations.models import Quotation
from app.modules.sales.models import SalesOrder


def list_quotations(db: Session, *, offset: int = 0, limit: int = 50) -> list[Quotation]:
    statement = (
        select(Quotation)
        .options(selectinload(Quotation.lines))
        .order_by(Quotation.doc_date.desc(), Quotation.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(statement))


def get_quotation(
    db: Session, quotation_id: int, *, for_update: bool = False
) -> Quotation | None:
    statement = (
        select(Quotation)
        .options(selectinload(Quotation.lines))
        .where(Quotation.id == quotation_id)
    )
    if for_update:
        statement = statement.with_for_update()
    return db.scalar(statement)


def get_accepted_quotation_for_update(db: Session, quotation_id: int) -> Quotation | None:
    statement = (
        select(Quotation)
        .options(selectinload(Quotation.lines), selectinload(Quotation.sales_order))
        .where(Quotation.id == quotation_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return db.scalar(statement)


def get_sales_order_id(db: Session, quotation_id: int) -> int | None:
    return db.scalar(
        select(SalesOrder.id).where(SalesOrder.quotation_id == quotation_id)
    )
