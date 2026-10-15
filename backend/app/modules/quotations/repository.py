from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.modules.quotations.models import Quotation


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
