from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.inventory.models import StockBalance, StockTransaction


def get_balance(
    db: Session, product_id: int, warehouse_id: int, *, for_update: bool = False
) -> StockBalance | None:
    statement = select(StockBalance).where(
        StockBalance.product_id == product_id,
        StockBalance.warehouse_id == warehouse_id,
    )
    if for_update:
        statement = statement.with_for_update()
    return db.scalar(statement)


def list_balances(
    db: Session,
    *,
    product_id: int | None = None,
    warehouse_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
) -> list[StockBalance]:
    statement = select(StockBalance)
    if product_id is not None:
        statement = statement.where(StockBalance.product_id == product_id)
    if warehouse_id is not None:
        statement = statement.where(StockBalance.warehouse_id == warehouse_id)
    return list(
        db.scalars(
            statement.order_by(StockBalance.product_id, StockBalance.warehouse_id)
            .offset(offset)
            .limit(limit)
        )
    )


def list_transactions(
    db: Session,
    *,
    product_id: int,
    warehouse_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
) -> list[StockTransaction]:
    statement = select(StockTransaction).where(StockTransaction.product_id == product_id)
    if warehouse_id is not None:
        statement = statement.where(StockTransaction.warehouse_id == warehouse_id)
    return list(
        db.scalars(
            statement.order_by(StockTransaction.txn_date.desc(), StockTransaction.id.desc())
            .offset(offset)
            .limit(limit)
        )
    )
