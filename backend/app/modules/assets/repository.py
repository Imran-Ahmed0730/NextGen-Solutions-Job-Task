from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.modules.assets.models import Asset


def list_assets(db: Session, *, include_inactive: bool, offset: int, limit: int) -> list[Asset]:
    statement = select(Asset).options(
        selectinload(Asset.assignments), selectinload(Asset.maintenance)
    )
    if not include_inactive:
        statement = statement.where(Asset.is_active.is_(True), Asset.deleted_at.is_(None))
    return list(db.scalars(statement.order_by(Asset.name, Asset.id).offset(offset).limit(limit)))


def get_asset(db: Session, asset_id: int, *, for_update: bool = False) -> Asset | None:
    statement = (
        select(Asset)
        .options(selectinload(Asset.assignments), selectinload(Asset.maintenance))
        .where(Asset.id == asset_id)
    )
    if for_update:
        statement = statement.with_for_update()
    return db.scalar(statement)


def get_asset_by_code(
    db: Session, asset_code: str, *, exclude_id: int | None = None
) -> Asset | None:
    statement = select(Asset).where(func.lower(Asset.asset_code) == asset_code.lower())
    if exclude_id is not None:
        statement = statement.where(Asset.id != exclude_id)
    return db.scalar(statement)
