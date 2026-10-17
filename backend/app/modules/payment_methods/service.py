from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.payment_methods import repository
from app.modules.payment_methods.models import PaymentMethod, PaymentMethodType


def list_payment_methods(
    db: Session, *, include_inactive: bool = False, offset: int = 0, limit: int = 50
) -> list[PaymentMethod]:
    return repository.list_payment_methods(
        db, include_inactive=include_inactive, offset=offset, limit=limit
    )


def get_payment_method(db: Session, payment_method_id: int) -> PaymentMethod | None:
    return repository.get_payment_method(db, payment_method_id)


def create_payment_method(
    db: Session, data: dict[str, object], actor: User, ip: str | None = None
) -> PaymentMethod:
    name = _validate_name(data.get("name"))
    method_type = _validate_type(data.get("type"))
    if not isinstance(data.get("is_active", True), bool):
        raise HTTPException(status_code=422, detail="is_active must be a boolean")

    payment_method = PaymentMethod(
        name=name,
        type=method_type,
        is_active=bool(data.get("is_active", True)),
    )
    db.add(payment_method)
    db.flush()
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="payment_method",
        entity_id=payment_method.id,
        action="CREATE",
        after=_snapshot(payment_method),
        ip=ip,
    )
    db.commit()
    db.refresh(payment_method)
    return payment_method


def update_payment_method(
    db: Session,
    payment_method: PaymentMethod,
    data: dict[str, object],
    actor: User,
    ip: str | None = None,
) -> PaymentMethod:
    if payment_method.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Payment method not found")

    name = payment_method.name
    if "name" in data:
        name = _validate_name(data["name"])

    method_type = payment_method.type
    if "type" in data:
        method_type = _validate_type(data["type"])

    is_active = payment_method.is_active
    if "is_active" in data:
        value = data["is_active"]
        if not isinstance(value, bool):
            raise HTTPException(status_code=422, detail="is_active must be a boolean")
        is_active = value

    before = _snapshot(payment_method)
    payment_method.name = name
    payment_method.type = method_type
    payment_method.is_active = is_active
    db.flush()
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="payment_method",
        entity_id=payment_method.id,
        action=(
            "STATUS"
            if is_active != before["is_active"]
            and name == before["name"]
            and method_type == before["type"]
            else "UPDATE"
        ),
        before=before,
        after=_snapshot(payment_method),
        ip=ip,
    )
    db.commit()
    db.refresh(payment_method)
    return payment_method


def delete_payment_method(
    db: Session, payment_method: PaymentMethod, actor: User, ip: str | None = None
) -> PaymentMethod:
    if payment_method.deleted_at is not None:
        return payment_method
    before = _snapshot(payment_method)
    payment_method.is_active = False
    payment_method.deleted_at = datetime.now(UTC)
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="payment_method",
        entity_id=payment_method.id,
        action="DELETE",
        before=before,
        after=_snapshot(payment_method),
        ip=ip,
    )
    db.commit()
    db.refresh(payment_method)
    return payment_method


def activate_payment_method(
    db: Session, payment_method: PaymentMethod, actor: User, ip: str | None = None
) -> PaymentMethod:
    if payment_method.is_active and payment_method.deleted_at is None:
        return payment_method
    before = _snapshot(payment_method)
    payment_method.is_active = True
    setattr(payment_method, "deleted_at", None)
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="payment_method",
        entity_id=payment_method.id,
        action="STATUS",
        before=before,
        after=_snapshot(payment_method),
        ip=ip,
    )
    db.commit()
    db.refresh(payment_method)
    return payment_method


def _validate_name(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=422, detail="Payment method name is required")
    name = value.strip()
    if len(name) > 100:
        raise HTTPException(status_code=422, detail="Payment method name is too long")
    return name


def _validate_type(value: object) -> PaymentMethodType:
    try:
        return value if isinstance(value, PaymentMethodType) else PaymentMethodType(str(value))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="Payment method type is not valid") from exc


def _snapshot(payment_method: PaymentMethod) -> dict[str, object]:
    return {
        "name": payment_method.name,
        "type": payment_method.type.value
        if hasattr(payment_method.type, "value")
        else str(payment_method.type),
        "is_active": payment_method.is_active,
        "deleted_at": payment_method.deleted_at.isoformat() if payment_method.deleted_at else None,
    }
