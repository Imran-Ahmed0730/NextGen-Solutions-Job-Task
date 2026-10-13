from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.payment_methods.models import PaymentMethod


def list_payment_methods(
    db: Session, *, include_inactive: bool = False, offset: int = 0, limit: int = 50
) -> list[PaymentMethod]:
    statement = select(PaymentMethod)
    if not include_inactive:
        statement = statement.where(
            PaymentMethod.is_active.is_(True), PaymentMethod.deleted_at.is_(None)
        )
    return list(
        db.scalars(
            statement.order_by(PaymentMethod.name, PaymentMethod.id).offset(offset).limit(limit)
        )
    )


def get_payment_method(db: Session, payment_method_id: int) -> PaymentMethod | None:
    return db.get(PaymentMethod, payment_method_id)