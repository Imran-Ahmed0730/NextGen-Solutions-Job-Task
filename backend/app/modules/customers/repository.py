from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.customers.models import Customer


def list_customers(
    db: Session, *, include_inactive: bool = False, offset: int = 0, limit: int = 50
) -> list[Customer]:
    statement = select(Customer)
    if not include_inactive:
        statement = statement.where(
            Customer.is_active.is_(True), Customer.deleted_at.is_(None)
        )
    return list(
        db.scalars(
            statement.order_by(Customer.name, Customer.id).offset(offset).limit(limit)
        )
    )


def get_customer(db: Session, customer_id: int) -> Customer | None:
    return db.get(Customer, customer_id)


def get_customer_by_code(db: Session, code: str) -> Customer | None:
    return db.scalar(select(Customer).where(Customer.code == code))