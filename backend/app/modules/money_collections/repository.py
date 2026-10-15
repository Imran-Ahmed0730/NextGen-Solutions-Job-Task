from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.customers.models import Customer
from app.modules.money_collections.models import CustomerCollection


def list_collections(db: Session, *, offset: int, limit: int) -> list[CustomerCollection]:
    statement = (
        select(CustomerCollection)
        .order_by(CustomerCollection.doc_date.desc(), CustomerCollection.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(statement))


def get_customer_for_update(db: Session, customer_id: int) -> Customer | None:
    return db.scalar(
        select(Customer)
        .where(Customer.id == customer_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def list_customer_collections(db: Session, customer_id: int) -> list[CustomerCollection]:
    statement = (
        select(CustomerCollection)
        .where(CustomerCollection.customer_id == customer_id)
        .order_by(CustomerCollection.doc_date, CustomerCollection.id)
    )
    return list(db.scalars(statement))
