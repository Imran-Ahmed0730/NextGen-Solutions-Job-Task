from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from app.modules.physical_counts.models import PhysicalCount, PhysicalCountLine
from app.modules.products.models import Product


def list_product_ids_for_count(db: Session) -> list[int]:
    statement = (
        select(Product.id)
        .where(
            Product.is_stocked.is_(True),
            Product.is_active.is_(True),
            Product.deleted_at.is_(None),
        )
        .order_by(Product.id)
    )
    return list(db.scalars(statement))


def list_counts(
    db: Session, *, offset: int = 0, limit: int = 50
) -> list[tuple[PhysicalCount, int, int]]:
    counted_lines = func.sum(case((PhysicalCountLine.counted_qty.is_not(None), 1), else_=0))
    statement = (
        select(
            PhysicalCount,
            func.count(PhysicalCountLine.id),
            counted_lines,
        )
        .outerjoin(PhysicalCountLine, PhysicalCountLine.count_id == PhysicalCount.id)
        .group_by(PhysicalCount.id)
        .order_by(PhysicalCount.created_at.desc(), PhysicalCount.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return [
        (physical_count, total_lines, counted_lines or 0)
        for physical_count, total_lines, counted_lines in db.execute(statement)
    ]


def get_count(db: Session, count_id: int, *, for_update: bool = False) -> PhysicalCount | None:
    statement = (
        select(PhysicalCount)
        .options(selectinload(PhysicalCount.lines).joinedload(PhysicalCountLine.product))
        .where(PhysicalCount.id == count_id)
    )
    if for_update:
        statement = statement.with_for_update()
    physical_count = db.scalar(statement)
    if physical_count is not None and for_update:
        db.scalars(
            select(PhysicalCountLine)
            .where(PhysicalCountLine.count_id == count_id)
            .order_by(PhysicalCountLine.product_id)
            .with_for_update()
        ).all()
    return physical_count
