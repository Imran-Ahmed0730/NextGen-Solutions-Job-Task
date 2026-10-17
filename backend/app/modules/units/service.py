from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.units import repository
from app.modules.units.models import Unit


def list_units(
    db: Session, *, include_inactive: bool = False, offset: int = 0, limit: int = 50
) -> list[Unit]:
    return repository.list_units(db, include_inactive=include_inactive, offset=offset, limit=limit)


def create_unit(db: Session, data: dict[str, object], actor: User, ip: str | None = None) -> Unit:
    name = str(data["name"]).strip()
    code = str(data["code"]).strip()
    _validate_name_and_code(name, code)
    _ensure_code_available(db, code)

    unit = Unit(name=name, code=code, allow_decimal=bool(data.get("allow_decimal", False)))
    db.add(unit)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise _duplicate_code_error() from exc

    record_audit(
        db,
        actor_id=actor.id,
        entity_type="unit",
        entity_id=unit.id,
        action="CREATE",
        after=_snapshot(unit),
        ip=ip,
    )
    db.commit()
    db.refresh(unit)
    return unit


def update_unit(
    db: Session,
    unit: Unit,
    data: dict[str, object],
    actor: User,
    ip: str | None = None,
) -> Unit:
    if unit.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Unit not found")

    name = unit.name
    code = unit.code
    allow_decimal = unit.allow_decimal
    if "name" in data:
        value = data["name"]
        if not isinstance(value, str):
            raise HTTPException(status_code=422, detail="Unit name is required")
        name = value.strip()
    if "code" in data:
        value = data["code"]
        if not isinstance(value, str):
            raise HTTPException(status_code=422, detail="Unit code is required")
        code = value.strip()
    if "allow_decimal" in data:
        value = data["allow_decimal"]
        if not isinstance(value, bool):
            raise HTTPException(status_code=422, detail="allow_decimal must be a boolean")
        allow_decimal = value

    _validate_name_and_code(name, code)
    _ensure_code_available(db, code, exclude_id=unit.id)
    before = _snapshot(unit)
    unit.name = name
    unit.code = code
    unit.allow_decimal = allow_decimal
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise _duplicate_code_error() from exc

    record_audit(
        db,
        actor_id=actor.id,
        entity_type="unit",
        entity_id=unit.id,
        action="UPDATE",
        before=before,
        after=_snapshot(unit),
        ip=ip,
    )
    db.commit()
    db.refresh(unit)
    return unit


def delete_unit(db: Session, unit: Unit, actor: User, ip: str | None = None) -> Unit:
    if unit.deleted_at is not None:
        return unit
    before = _snapshot(unit)
    unit.is_active = False
    unit.deleted_at = datetime.now(UTC)
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="unit",
        entity_id=unit.id,
        action="DELETE",
        before=before,
        after=_snapshot(unit),
        ip=ip,
    )
    db.commit()
    db.refresh(unit)
    return unit


def activate_unit(db: Session, unit: Unit, actor: User, ip: str | None = None) -> Unit:
    if unit.is_active and unit.deleted_at is None:
        return unit
    before = _snapshot(unit)
    unit.is_active = True
    setattr(unit, "deleted_at", None)
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="unit",
        entity_id=unit.id,
        action="STATUS",
        before=before,
        after=_snapshot(unit),
        ip=ip,
    )
    db.commit()
    db.refresh(unit)
    return unit


def _validate_name_and_code(name: str, code: str) -> None:
    if not name:
        raise HTTPException(status_code=422, detail="Unit name is required")
    if not code:
        raise HTTPException(status_code=422, detail="Unit code is required")


def _ensure_code_available(db: Session, code: str, *, exclude_id: int | None = None) -> None:
    if repository.get_unit_by_code(db, code, exclude_id=exclude_id) is not None:
        raise _duplicate_code_error()


def _duplicate_code_error() -> HTTPException:
    return HTTPException(status_code=409, detail="Unit code is already in use")


def _snapshot(unit: Unit) -> dict[str, object]:
    return {
        "name": unit.name,
        "code": unit.code,
        "allow_decimal": unit.allow_decimal,
        "is_active": unit.is_active,
        "deleted_at": unit.deleted_at.isoformat() if unit.deleted_at else None,
    }
