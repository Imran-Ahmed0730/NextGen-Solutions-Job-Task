from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.expense_categories.models import ExpenseCategory


def list_categories(
    db: Session, *, include_inactive: bool = False, offset: int = 0, limit: int = 50
) -> list[ExpenseCategory]:
    statement = select(ExpenseCategory)
    if not include_inactive:
        statement = statement.where(
            ExpenseCategory.is_active.is_(True), ExpenseCategory.deleted_at.is_(None)
        )
    return list(
        db.scalars(
            statement.order_by(ExpenseCategory.name, ExpenseCategory.id)
            .offset(offset)
            .limit(limit)
        )
    )


def get_category(db: Session, category_id: int) -> ExpenseCategory | None:
    return db.get(ExpenseCategory, category_id)