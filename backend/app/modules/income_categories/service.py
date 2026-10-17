from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.income_categories import repository
from app.modules.income_categories.models import IncomeCategory


def list_categories(
    db: Session, *, include_inactive: bool = False, offset: int = 0, limit: int = 50
) -> list[IncomeCategory]:
    return repository.list_categories(
        db, include_inactive=include_inactive, offset=offset, limit=limit
    )


def get_category(db: Session, category_id: int) -> IncomeCategory | None:
    return repository.get_category(db, category_id)


def create_category(
    db: Session, data: dict[str, object], actor: User, ip: str | None = None
) -> IncomeCategory:
    name = _validate_name(data.get("name"))
    is_active = data.get("is_active", True)
    if not isinstance(is_active, bool):
        raise HTTPException(status_code=422, detail="is_active must be a boolean")

    category = IncomeCategory(name=name, is_active=is_active)
    db.add(category)
    db.flush()
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="income_category",
        entity_id=category.id,
        action="CREATE",
        after=_snapshot(category),
        ip=ip,
    )
    db.commit()
    db.refresh(category)
    return category


def update_category(
    db: Session,
    category: IncomeCategory,
    data: dict[str, object],
    actor: User,
    ip: str | None = None,
) -> IncomeCategory:
    if category.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Income category not found")

    name = category.name
    if "name" in data:
        name = _validate_name(data["name"])

    is_active = category.is_active
    if "is_active" in data:
        value = data["is_active"]
        if not isinstance(value, bool):
            raise HTTPException(status_code=422, detail="is_active must be a boolean")
        is_active = value

    before = _snapshot(category)
    category.name = name
    category.is_active = is_active
    db.flush()
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="income_category",
        entity_id=category.id,
        action=(
            "STATUS" if is_active != before["is_active"] and name == before["name"] else "UPDATE"
        ),
        before=before,
        after=_snapshot(category),
        ip=ip,
    )
    db.commit()
    db.refresh(category)
    return category


def delete_category(
    db: Session, category: IncomeCategory, actor: User, ip: str | None = None
) -> IncomeCategory:
    if category.deleted_at is not None:
        return category
    before = _snapshot(category)
    category.is_active = False
    category.deleted_at = datetime.now(UTC)
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="income_category",
        entity_id=category.id,
        action="DELETE",
        before=before,
        after=_snapshot(category),
        ip=ip,
    )
    db.commit()
    db.refresh(category)
    return category


def activate_category(
    db: Session, category: IncomeCategory, actor: User, ip: str | None = None
) -> IncomeCategory:
    if category.is_active and category.deleted_at is None:
        return category
    before = _snapshot(category)
    category.is_active = True
    setattr(category, "deleted_at", None)
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="income_category",
        entity_id=category.id,
        action="STATUS",
        before=before,
        after=_snapshot(category),
        ip=ip,
    )
    db.commit()
    db.refresh(category)
    return category


def _validate_name(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=422, detail="Income category name is required")
    name = value.strip()
    if len(name) > 100:
        raise HTTPException(status_code=422, detail="Income category name is too long")
    return name


def _snapshot(category: IncomeCategory) -> dict[str, object]:
    return {
        "name": category.name,
        "is_active": category.is_active,
        "deleted_at": category.deleted_at.isoformat() if category.deleted_at else None,
    }
