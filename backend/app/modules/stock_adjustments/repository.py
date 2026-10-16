from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.modules.stock_adjustments.models import StockAdjustment


def list_adjustments(db: Session, *, offset: int = 0, limit: int = 50) -> list[StockAdjustment]:
    statement = (
        select(StockAdjustment)
        .options(selectinload(StockAdjustment.lines))
        .order_by(StockAdjustment.doc_date.desc(), StockAdjustment.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(statement))


def get_adjustment(db: Session, adjustment_id: int) -> StockAdjustment | None:
    statement = (
        select(StockAdjustment)
        .options(selectinload(StockAdjustment.lines))
        .where(StockAdjustment.id == adjustment_id)
    )
    return db.scalar(statement)


def get_adjustment_for_update(db: Session, adjustment_id: int) -> StockAdjustment | None:
    statement = (
        select(StockAdjustment)
        .options(selectinload(StockAdjustment.lines))
        .where(StockAdjustment.id == adjustment_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return db.scalar(statement)
