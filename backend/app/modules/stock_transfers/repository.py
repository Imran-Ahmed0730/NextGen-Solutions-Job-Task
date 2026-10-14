from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.modules.stock_transfers.models import StockTransfer


def list_transfers(db: Session, *, offset: int = 0, limit: int = 50) -> list[StockTransfer]:
    statement = (
        select(StockTransfer)
        .options(selectinload(StockTransfer.lines))
        .order_by(StockTransfer.doc_date.desc(), StockTransfer.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(statement))


def get_transfer(db: Session, transfer_id: int) -> StockTransfer | None:
    statement = (
        select(StockTransfer)
        .options(selectinload(StockTransfer.lines))
        .where(StockTransfer.id == transfer_id)
    )
    return db.scalar(statement)
