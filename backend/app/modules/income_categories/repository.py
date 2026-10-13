from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.income_categories.models import IncomeCategory


def list_categories(
    db: Session, *, include_inactive: bool = False, offset: int = 0, limit: int = 50
) -> list[IncomeCategory]:
    statement = select(IncomeCategory)
    if not include_inactive:
        statement = statement.where(
            IncomeCategory.is_active.is_(True), IncomeCategory.deleted_at.is_(None)
        )
    return list(
        db.scalars(
            statement.order_by(IncomeCategory.name, IncomeCategory.id)
            .offset(offset)
            .limit(limit)
        )
    )


def get_category(db: Session, category_id: int) -> IncomeCategory | None:
    return db.get(IncomeCategory, category_id)