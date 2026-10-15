from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.expense_categories.models import ExpenseCategory
from app.modules.expenses.models import Expense
from app.modules.money_accounts.models import MoneyAccount


def list_expenses(db: Session, *, offset: int = 0, limit: int = 50) -> list[Expense]:
    stmt = (
        select(Expense)
        .order_by(Expense.doc_date.desc(), Expense.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(stmt))


def get_expense(db: Session, expense_id: int) -> Expense | None:
    return db.get(Expense, expense_id)


def get_category_for_update(db: Session, category_id: int) -> ExpenseCategory | None:
    return db.scalar(
        select(ExpenseCategory)
        .where(ExpenseCategory.id == category_id)
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

