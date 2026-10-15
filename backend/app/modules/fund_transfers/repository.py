from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.fund_transfers.models import FundTransfer
from app.modules.money_accounts.models import MoneyAccount


def list_transfers(db: Session, *, offset: int = 0, limit: int = 50) -> list[FundTransfer]:
    stmt = (
        select(FundTransfer)
        .order_by(FundTransfer.doc_date.desc(), FundTransfer.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(stmt))


def get_transfer(db: Session, transfer_id: int) -> FundTransfer | None:
    return db.get(FundTransfer, transfer_id)


def get_account_for_update(db: Session, account_id: int) -> MoneyAccount | None:
    return db.scalar(
        select(MoneyAccount)
        .where(MoneyAccount.id == account_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )

