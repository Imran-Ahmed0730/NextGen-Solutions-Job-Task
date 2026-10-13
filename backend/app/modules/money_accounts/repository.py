from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.money_accounts.models import MoneyAccount


def list_money_accounts(
    db: Session, *, include_inactive: bool = False, offset: int = 0, limit: int = 50
) -> list[MoneyAccount]:
    statement = select(MoneyAccount)
    if not include_inactive:
        statement = statement.where(
            MoneyAccount.is_active.is_(True), MoneyAccount.deleted_at.is_(None)
        )
    return list(
        db.scalars(
            statement.order_by(MoneyAccount.name, MoneyAccount.id).offset(offset).limit(limit)
        )
    )


def get_money_account(db: Session, account_id: int) -> MoneyAccount | None:
    return db.get(MoneyAccount, account_id)