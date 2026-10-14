from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.modules.suppliers.models import Supplier


def list_suppliers(
    db: Session,
    *,
    include_inactive: bool = False,
    offset: int = 0,
    limit: int = 50,
    search: str | None = None,
) -> list[Supplier]:
    statement = select(Supplier)
    if not include_inactive:
        statement = statement.where(
            Supplier.is_active.is_(True), Supplier.deleted_at.is_(None)
        )
    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                Supplier.code.ilike(pattern),
                Supplier.name.ilike(pattern),
                Supplier.mobile.ilike(pattern),
                Supplier.email.ilike(pattern),
            )
        )
    return list(
        db.scalars(
            statement.order_by(Supplier.name, Supplier.id).offset(offset).limit(limit)
        )
    )


def get_supplier(db: Session, supplier_id: int) -> Supplier | None:
    return db.get(Supplier, supplier_id)


def get_supplier_by_code(db: Session, code: str) -> Supplier | None:
    return db.scalar(select(Supplier).where(Supplier.code == code))