from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.modules.boms.models import BOM


def list_boms(
    db: Session, *, include_inactive: bool, offset: int, limit: int
) -> list[BOM]:
    statement = select(BOM).options(joinedload(BOM.finished_product))
    if not include_inactive:
        statement = statement.where(BOM.is_active.is_(True), BOM.deleted_at.is_(None))
    return list(
        db.scalars(statement.order_by(BOM.code, BOM.id).offset(offset).limit(limit))
    )


def get_bom(db: Session, bom_id: int, *, for_update: bool = False) -> BOM | None:
    statement = (
        select(BOM)
        .options(joinedload(BOM.finished_product))
        .where(BOM.id == bom_id)
    )
    if for_update:
        statement = statement.with_for_update()
    return db.scalar(statement)


def get_bom_by_code(
    db: Session, code: str, *, exclude_id: int | None = None
) -> BOM | None:
    statement = select(BOM).where(func.lower(BOM.code) == code.lower())
    if exclude_id is not None:
        statement = statement.where(BOM.id != exclude_id)
    return db.scalar(statement)
