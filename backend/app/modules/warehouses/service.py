from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.warehouses import repository
from app.modules.warehouses.models import Warehouse


def list_warehouses(
    db: Session, *, include_inactive: bool = False, offset: int = 0, limit: int = 50
) -> list[Warehouse]:
    return repository.list_warehouses(
        db, include_inactive=include_inactive, offset=offset, limit=limit
    )


def get_warehouse(db: Session, warehouse_id: int) -> Warehouse | None:
    return repository.get_warehouse(db, warehouse_id)


def get_active_warehouse(db: Session, warehouse_id: int) -> Warehouse | None:
    warehouse = repository.get_warehouse(db, warehouse_id)
    if warehouse is None or not warehouse.is_active or warehouse.deleted_at is not None:
        return None
    return warehouse


def create_warehouse(
    db: Session, data: dict[str, object], actor: User, ip: str | None = None
) -> Warehouse:
    name = _validate_name(data.get("name"))
    code = _validate_code(data.get("code"))
    address = _validate_address(data.get("address"))
    if not isinstance(data.get("is_active", True), bool):
        raise HTTPException(status_code=422, detail="is_active must be a boolean")
    is_default = data.get("is_default", False)
    if not isinstance(is_default, bool):
        raise HTTPException(status_code=422, detail="is_default must be a boolean")

    _ensure_code_available(db, code)

    warehouse = Warehouse(
        name=name,
        code=code,
        address=address,
        is_default=is_default,
        is_active=bool(data.get("is_active", True)),
    )
    if is_default:
        _clear_other_defaults(db)
    db.add(warehouse)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise _duplicate_code_error() from exc

    record_audit(
        db,
        actor_id=actor.id,
        entity_type="warehouse",
        entity_id=warehouse.id,
        action="CREATE",
        after=_snapshot(warehouse),
        ip=ip,
    )
    db.commit()
    db.refresh(warehouse)
    return warehouse


def update_warehouse(
    db: Session,
    warehouse: Warehouse,
    data: dict[str, object],
    actor: User,
    ip: str | None = None,
) -> Warehouse:
    if warehouse.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Warehouse not found")

    name = warehouse.name
    if "name" in data:
        name = _validate_name(data["name"])

    code = warehouse.code
    if "code" in data:
        code = _validate_code(data["code"])
        if code != warehouse.code:
            _ensure_code_available(db, code, exclude_id=warehouse.id)

    address = warehouse.address
    if "address" in data:
        address = _validate_address(data["address"])

    is_active = warehouse.is_active
    if "is_active" in data:
        value = data["is_active"]
        if not isinstance(value, bool):
            raise HTTPException(status_code=422, detail="is_active must be a boolean")
        is_active = value

    is_default = warehouse.is_default
    if "is_default" in data:
        value = data["is_default"]
        if not isinstance(value, bool):
            raise HTTPException(status_code=422, detail="is_default must be a boolean")
        is_default = value

    before = _snapshot(warehouse)
    warehouse.name = name
    warehouse.code = code
    warehouse.address = address
    warehouse.is_active = is_active
    warehouse.is_default = is_default
    if is_default:
        _clear_other_defaults(db, exclude_id=warehouse.id)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise _duplicate_code_error() from exc

    record_audit(
        db,
        actor_id=actor.id,
        entity_type="warehouse",
        entity_id=warehouse.id,
        action=(
            "STATUS"
            if is_active != before["is_active"]
            and name == before["name"]
            and code == before["code"]
            and address == before["address"]
            and is_default == before["is_default"]
            else "UPDATE"
        ),
        before=before,
        after=_snapshot(warehouse),
        ip=ip,
    )
    db.commit()
    db.refresh(warehouse)
    return warehouse


def delete_warehouse(
    db: Session, warehouse: Warehouse, actor: User, ip: str | None = None
) -> Warehouse:
    if warehouse.deleted_at is not None:
        return warehouse
    before = _snapshot(warehouse)
    warehouse.is_active = False
    warehouse.is_default = False
    warehouse.deleted_at = datetime.now(UTC)
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="warehouse",
        entity_id=warehouse.id,
        action="DELETE",
        before=before,
        after=_snapshot(warehouse),
        ip=ip,
    )
    db.commit()
    db.refresh(warehouse)
    return warehouse


def activate_warehouse(
    db: Session, warehouse: Warehouse, actor: User, ip: str | None = None
) -> Warehouse:
    if warehouse.is_active and warehouse.deleted_at is None:
        return warehouse
    before = _snapshot(warehouse)
    warehouse.is_active = True
    setattr(warehouse, "deleted_at", None)
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="warehouse",
        entity_id=warehouse.id,
        action="STATUS",
        before=before,
        after=_snapshot(warehouse),
        ip=ip,
    )
    db.commit()
    db.refresh(warehouse)
    return warehouse


def _clear_other_defaults(db: Session, *, exclude_id: int | None = None) -> None:
    for other in repository.list_default_warehouses(db, exclude_id=exclude_id):
        other.is_default = False


def _validate_name(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=422, detail="Warehouse name is required")
    name = value.strip()
    if len(name) > 100:
        raise HTTPException(status_code=422, detail="Warehouse name is too long")
    return name


def _validate_code(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=422, detail="Warehouse code is required")
    code = value.strip()
    if len(code) > 30:
        raise HTTPException(status_code=422, detail="Warehouse code is too long")
    return code


def _validate_address(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise HTTPException(status_code=422, detail="Warehouse address must be text")
    address = value.strip()
    if not address:
        return None
    if len(address) > 255:
        raise HTTPException(status_code=422, detail="Warehouse address is too long")
    return address


def _ensure_code_available(db: Session, code: str, *, exclude_id: int | None = None) -> None:
    if repository.get_warehouse_by_code(db, code, exclude_id=exclude_id) is not None:
        raise _duplicate_code_error()


def _duplicate_code_error() -> HTTPException:
    return HTTPException(status_code=409, detail="Warehouse code is already in use")


def _snapshot(warehouse: Warehouse) -> dict[str, object]:
    return {
        "name": warehouse.name,
        "code": warehouse.code,
        "address": warehouse.address,
        "is_default": warehouse.is_default,
        "is_active": warehouse.is_active,
        "deleted_at": warehouse.deleted_at.isoformat() if warehouse.deleted_at else None,
    }
