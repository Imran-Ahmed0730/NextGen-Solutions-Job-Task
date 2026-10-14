from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.modules.inventory.models import StockBalance, StockReservation, StockTransaction


def get_reservation_for_update(db: Session, reservation_id: int) -> StockReservation | None:
    return db.scalar(
        select(StockReservation).where(StockReservation.id == reservation_id).with_for_update()
    )


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


def list_balances_for_products(
    db: Session,
    *,
    product_ids: list[int],
    warehouse_ids: list[int],
) -> list[StockBalance]:
    if not product_ids or not warehouse_ids:
        return []
    statement = select(StockBalance).where(
        StockBalance.product_id.in_(product_ids),
        StockBalance.warehouse_id.in_(warehouse_ids),
    )
    return list(db.scalars(statement))


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


def list_ledger_entries(
    db: Session,
    *,
    product_id: int,
    warehouse_id: int | None = None,
    date_from: datetime | None = None,
    date_to_exclusive: datetime | None = None,
    offset: int = 0,
    limit: int = 100,
) -> list[tuple[StockTransaction, Decimal]]:
    running_qty = (
        func.sum(StockTransaction.qty_signed)
        .over(
            partition_by=(StockTransaction.product_id, StockTransaction.warehouse_id),
            order_by=(StockTransaction.txn_date, StockTransaction.id),
            rows=(None, 0),
        )
        .label("running_qty")
    )
    ledger = (
        select(StockTransaction, running_qty)
        .where(StockTransaction.product_id == product_id)
        .subquery()
    )
    transaction = aliased(StockTransaction, ledger)
    statement = select(transaction, ledger.c.running_qty)
    if warehouse_id is not None:
        statement = statement.where(transaction.warehouse_id == warehouse_id)
    if date_from is not None:
        statement = statement.where(transaction.txn_date >= date_from)
    if date_to_exclusive is not None:
        statement = statement.where(transaction.txn_date < date_to_exclusive)
    statement = statement.order_by(transaction.txn_date.desc(), transaction.id.desc())
    statement = statement.offset(offset).limit(limit)
    return [(row, Decimal(running)) for row, running in db.execute(statement)]
