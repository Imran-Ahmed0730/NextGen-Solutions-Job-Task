from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.money_accounts.models import MoneyAccount
from app.modules.money_transactions.models import MoneyTransaction, MoneyTransactionType


def get_account_for_update(db: Session, account_id: int) -> MoneyAccount | None:
    return db.scalar(
        select(MoneyAccount)
        .where(MoneyAccount.id == account_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def get_account_balance(db: Session, account: MoneyAccount) -> Decimal:
    transaction_total = db.scalar(
        select(func.sum(MoneyTransaction.amount_signed)).where(
            MoneyTransaction.account_id == account.id
        )
    )
    return account.opening_balance + (transaction_total or Decimal("0.00"))


def get_account_balance_for_update(db: Session, account: MoneyAccount) -> Decimal:
    amounts = db.scalars(
        select(MoneyTransaction.amount_signed)
        .where(MoneyTransaction.account_id == account.id)
        .with_for_update()
    )
    transaction_total = sum(amounts, start=Decimal("0.00"))
    return account.opening_balance + transaction_total


def has_transactions(db: Session, account_id: int) -> bool:
    return (
        db.scalar(
            select(MoneyTransaction.id)
            .where(MoneyTransaction.account_id == account_id)
            .limit(1)
            .with_for_update()
        )
        is not None
    )


def get_account_for_balance(db: Session, account_id: int) -> MoneyAccount | None:
    return db.get(MoneyAccount, account_id)


def create_transaction(
    db: Session,
    *,
    txn_date: datetime,
    account_id: int,
    amount_signed: Decimal,
    txn_type: MoneyTransactionType,
    source_type: str | None,
    source_id: int | None,
    party_type: str | None,
    party_id: int | None,
    note: str | None,
    created_by: int,
) -> MoneyTransaction:
    transaction = MoneyTransaction(
        txn_date=txn_date,
        account_id=account_id,
        amount_signed=amount_signed,
        txn_type=txn_type,
        source_type=source_type,
        source_id=source_id,
        party_type=party_type,
        party_id=party_id,
        note=note,
        created_by=created_by,
    )
    db.add(transaction)
    db.flush()
    return transaction


def list_account_transactions(
    db: Session,
    account: MoneyAccount,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> tuple[Decimal, list[MoneyTransaction]]:
    prior_sum = Decimal("0.00")
    if from_date is not None:
        prior_total = db.scalar(
            select(func.sum(MoneyTransaction.amount_signed)).where(
                MoneyTransaction.account_id == account.id,
                MoneyTransaction.txn_date < from_date,
            )
        )
        if prior_total is not None:
            prior_sum = prior_total

    opening_balance = account.opening_balance + prior_sum

    stmt = select(MoneyTransaction).where(MoneyTransaction.account_id == account.id)
    if from_date is not None:
        stmt = stmt.where(MoneyTransaction.txn_date >= from_date)
    if to_date is not None:
        stmt = stmt.where(MoneyTransaction.txn_date <= to_date)
    stmt = stmt.order_by(MoneyTransaction.txn_date.asc(), MoneyTransaction.id.asc())

    transactions = list(db.scalars(stmt))
    return opening_balance, transactions

