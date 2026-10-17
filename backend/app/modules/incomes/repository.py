from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.income_categories.models import IncomeCategory
from app.modules.incomes.models import Income
from app.modules.money_accounts.models import MoneyAccount


def list_incomes(db: Session, *, offset: int = 0, limit: int = 50) -> list[Income]:
    stmt = (
        select(Income)
        .order_by(Income.doc_date.desc(), Income.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(stmt))


def get_income(db: Session, income_id: int) -> Income | None:
    return db.get(Income, income_id)


def get_category_for_update(db: Session, category_id: int) -> IncomeCategory | None:
    return db.scalar(
        select(IncomeCategory)
        .where(IncomeCategory.id == category_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def get_account_for_update(db: Session, account_id: int) -> MoneyAccount | None:
    return db.scalar(
        select(MoneyAccount)
        .where(MoneyAccount.id == account_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
