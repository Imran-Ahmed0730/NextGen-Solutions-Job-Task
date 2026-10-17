from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.units.models import Unit


def list_units(db: Session, *, include_inactive: bool, offset: int, limit: int) -> list[Unit]:
    statement = select(Unit)
    if not include_inactive:
        statement = statement.where(Unit.is_active.is_(True), Unit.deleted_at.is_(None))
    return list(db.scalars(statement.order_by(Unit.name, Unit.id).offset(offset).limit(limit)))


def get_unit(db: Session, unit_id: int) -> Unit | None:
    return db.get(Unit, unit_id)


def get_unit_by_code(db: Session, code: str, *, exclude_id: int | None = None) -> Unit | None:
    statement = select(Unit).where(func.lower(Unit.code) == code.lower())
    if exclude_id is not None:
        statement = statement.where(Unit.id != exclude_id)
    return db.scalar(statement)
