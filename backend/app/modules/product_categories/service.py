from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.product_categories import repository
from app.modules.product_categories.models import ProductCategory


def list_categories(
    db: Session, *, include_inactive: bool = False, offset: int = 0, limit: int = 50
) -> list[ProductCategory]:
    return repository.list_categories(
        db, include_inactive=include_inactive, offset=offset, limit=limit
    )


def create_category(
    db: Session, data: dict[str, object], actor: User, ip: str | None = None
) -> ProductCategory:
    name = _validate_name(data.get("name"))
    parent_id = data.get("parent_id")
    if parent_id is not None and not isinstance(parent_id, int):
        raise HTTPException(status_code=422, detail="Parent category id must be an integer")
    _validate_parent(db, parent_id, exclude_id=None)

    is_active = data.get("is_active", True)
    if not isinstance(is_active, bool):
        raise HTTPException(status_code=422, detail="is_active must be a boolean")

    category = ProductCategory(name=name, parent_id=parent_id, is_active=is_active)
    db.add(category)
    db.flush()
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="product_category",
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
    category: ProductCategory,
    data: dict[str, object],
    actor: User,
    ip: str | None = None,
) -> ProductCategory:
    if category.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Product category not found")

    name = category.name
    if "name" in data:
        name = _validate_name(data["name"])

    parent_id = category.parent_id
    if "parent_id" in data:
        value = data["parent_id"]
        if value is not None and not isinstance(value, int):
            raise HTTPException(status_code=422, detail="Parent category id must be an integer")
        parent_id = value
        if parent_id != category.parent_id:
            _validate_parent(db, parent_id, exclude_id=category.id)

    is_active = category.is_active
    if "is_active" in data:
        value = data["is_active"]
        if not isinstance(value, bool):
            raise HTTPException(status_code=422, detail="is_active must be a boolean")
        is_active = value

    before = _snapshot(category)
    category.name = name
    category.parent_id = parent_id
    category.is_active = is_active
    db.flush()
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="product_category",
        entity_id=category.id,
        action=(
            "STATUS"
            if is_active != before["is_active"]
            and name == before["name"]
            and parent_id == before["parent_id"]
            else "UPDATE"
        ),
        before=before,
        after=_snapshot(category),
        ip=ip,
    )
    db.commit()
    db.refresh(category)
    return category


def delete_category(
    db: Session, category: ProductCategory, actor: User, ip: str | None = None
) -> ProductCategory:
    if category.deleted_at is not None:
        return category
    before = _snapshot(category)
    category.is_active = False
    category.deleted_at = datetime.now(UTC)
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="product_category",
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
    db: Session, category: ProductCategory, actor: User, ip: str | None = None
) -> ProductCategory:
    if category.is_active and category.deleted_at is None:
        return category
    before = _snapshot(category)
    category.is_active = True
    setattr(category, "deleted_at", None)
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="product_category",
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
        raise HTTPException(status_code=422, detail="Product category name is required")
    name = value.strip()
    if len(name) > 100:
        raise HTTPException(status_code=422, detail="Product category name is too long")
    return name


def _validate_parent(db: Session, parent_id: int | None, *, exclude_id: int | None) -> None:
    if parent_id is None:
        return
    parent = repository.get_category(db, parent_id)
    if parent is None or parent.deleted_at is not None or not parent.is_active:
        raise HTTPException(status_code=422, detail="Parent category is not available")

    visited: set[int] = set()
    current: ProductCategory | None = parent
    while current is not None:
        if current.id == exclude_id:
            raise HTTPException(status_code=422, detail="Category hierarchy cannot contain a cycle")
        if current.id in visited:
            raise HTTPException(
                status_code=409, detail="Existing category hierarchy contains a cycle"
            )
        visited.add(current.id)
        current = (
            repository.get_category(db, current.parent_id)
            if current.parent_id is not None
            else None
        )


def _snapshot(category: ProductCategory) -> dict[str, object]:
    return {
        "name": category.name,
        "parent_id": category.parent_id,
        "is_active": category.is_active,
        "deleted_at": category.deleted_at.isoformat() if category.deleted_at else None,
    }
