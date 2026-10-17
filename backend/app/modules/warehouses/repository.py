from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.warehouses.models import Warehouse


def list_warehouses(
    db: Session, *, include_inactive: bool = False, offset: int = 0, limit: int = 50
) -> list[Warehouse]:
    statement = select(Warehouse)
    if not include_inactive:
        statement = statement.where(Warehouse.is_active.is_(True), Warehouse.deleted_at.is_(None))
    return list(
        db.scalars(statement.order_by(Warehouse.name, Warehouse.id).offset(offset).limit(limit))
    )


def get_warehouse(db: Session, warehouse_id: int) -> Warehouse | None:
    return db.get(Warehouse, warehouse_id)


def get_warehouse_by_code(
    db: Session, code: str, *, exclude_id: int | None = None
) -> Warehouse | None:
    statement = select(Warehouse).where(func.lower(Warehouse.code) == code.lower())
    if exclude_id is not None:
        statement = statement.where(Warehouse.id != exclude_id)
    return db.scalar(statement)


def get_default_warehouse(db: Session) -> Warehouse | None:
    statement = select(Warehouse).where(
        Warehouse.is_default.is_(True),
        Warehouse.is_active.is_(True),
        Warehouse.deleted_at.is_(None),
    )
    return db.scalar(statement)


def list_default_warehouses(db: Session, *, exclude_id: int | None = None) -> list[Warehouse]:
    statement = select(Warehouse).where(Warehouse.is_default.is_(True))
    if exclude_id is not None:
        statement = statement.where(Warehouse.id != exclude_id)
    return list(db.scalars(statement))
