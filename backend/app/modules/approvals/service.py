from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.approvals import repository
from app.modules.approvals.models import ApprovalRule
from app.modules.auth.audit import record_audit
from app.modules.auth.models import User


def list_rules(db: Session, *, include_inactive: bool = False) -> list[ApprovalRule]:
    return repository.list_rules(db, include_inactive=include_inactive)


def list_active_roles(db: Session) -> list[dict[str, object]]:
    return [{"id": role.id, "name": role.name} for role in repository.list_active_roles(db)]


def create_rule(
    db: Session, data: dict[str, object], actor: User, ip: str | None = None
) -> ApprovalRule:
    doc_type = _document_type(data.get("doc_type"))
    min_amount = _threshold(data.get("min_amount"), "Minimum amount")
    max_amount = _optional_threshold(data.get("max_amount"), "Maximum amount")
    role_id = _role_id(data.get("approver_role_id"))
    _validate_range(min_amount, max_amount)
    role = repository.get_active_role(db, role_id, for_update=True)
    if role is None:
        raise HTTPException(status_code=404, detail="Active approver role not found")
    _ensure_no_overlap(db, doc_type, min_amount, max_amount)

    rule = ApprovalRule(
        doc_type=doc_type,
        min_amount=min_amount,
        max_amount=max_amount,
        approver_role_id=role_id,
        is_active=True,
    )
    db.add(rule)
    db.flush()
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="approval_rule",
        entity_id=rule.id,
        action="CREATE",
        after=_snapshot(rule),
        ip=ip,
    )
    db.commit()
    result = repository.get_rule(db, rule.id)
    if result is None:
        raise RuntimeError("Created approval rule could not be reloaded")
    return result


def update_rule(
    db: Session,
    rule_id: int,
    data: dict[str, object],
    actor: User,
    ip: str | None = None,
) -> ApprovalRule:
    rule = repository.get_rule(db, rule_id, for_update=True)
    if rule is None:
        raise HTTPException(status_code=404, detail="Approval rule not found")
    doc_type = _document_type(data.get("doc_type", rule.doc_type))
    min_amount = _threshold(data.get("min_amount", rule.min_amount), "Minimum amount")
    max_amount = _optional_threshold(data.get("max_amount", rule.max_amount), "Maximum amount")
    role_id = _role_id(data.get("approver_role_id", rule.approver_role_id))
    _validate_range(min_amount, max_amount)
    if repository.get_active_role(db, role_id, for_update=True) is None:
        raise HTTPException(status_code=404, detail="Active approver role not found")
    if rule.is_active:
        _ensure_no_overlap(db, doc_type, min_amount, max_amount, exclude_id=rule.id)

    before = _snapshot(rule)
    rule.doc_type = doc_type
    rule.min_amount = min_amount
    setattr(rule, "max_amount", max_amount)
    rule.approver_role_id = role_id
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="approval_rule",
        entity_id=rule.id,
        action="UPDATE",
        before=before,
        after=_snapshot(rule),
        ip=ip,
    )
    db.commit()
    result = repository.get_rule(db, rule.id)
    if result is None:
        raise RuntimeError("Updated approval rule could not be reloaded")
    return result


def set_rule_active(
    db: Session,
    rule_id: int,
    is_active: bool,
    actor: User,
    ip: str | None = None,
) -> ApprovalRule:
    rule = repository.get_rule(db, rule_id, for_update=True)
    if rule is None:
        raise HTTPException(status_code=404, detail="Approval rule not found")
    if rule.is_active == is_active:
        return rule
    if is_active:
        if repository.get_active_role(db, rule.approver_role_id, for_update=True) is None:
            raise HTTPException(status_code=409, detail="Approver role is inactive")
        _ensure_no_overlap(
            db,
            rule.doc_type,
            rule.min_amount,
            rule.max_amount,
            exclude_id=rule.id,
        )
    before = _snapshot(rule)
    rule.is_active = is_active
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="approval_rule",
        entity_id=rule.id,
        action="ACTIVATE" if is_active else "DEACTIVATE",
        before=before,
        after=_snapshot(rule),
        ip=ip,
    )
    db.commit()
    result = repository.get_rule(db, rule.id)
    if result is None:
        raise RuntimeError("Updated approval rule could not be reloaded")
    return result


def _ensure_no_overlap(
    db: Session,
    doc_type: str,
    min_amount: Decimal,
    max_amount: Decimal | None,
    *,
    exclude_id: int | None = None,
) -> None:
    for existing in repository.list_doc_type_rules_for_update(db, doc_type):
        if existing.id == exclude_id:
            continue
        lower_overlaps = existing.max_amount is None or min_amount <= existing.max_amount
        upper_overlaps = max_amount is None or existing.min_amount <= max_amount
        if lower_overlaps and upper_overlaps:
            raise HTTPException(
                status_code=409,
                detail=f"Approval amount range overlaps active rule {existing.id}",
            )


def _document_type(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=422, detail="Document type is required")
    normalized = value.strip().upper()
    if len(normalized) > 50 or not normalized[0].isalpha() or not all(
        char.isascii() and (char.isalnum() or char == "_") for char in normalized
    ):
        raise HTTPException(status_code=422, detail="Document type format is invalid")
    return normalized


def _threshold(value: object, label: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise HTTPException(status_code=422, detail=f"{label} must be a nonnegative amount")
    if len(value.as_tuple().digits) > 18 or value > Decimal("9999999999999999.99"):
        raise HTTPException(status_code=422, detail=f"{label} exceeds supported precision")
    try:
        if value.quantize(Decimal("0.01")) != value:
            raise HTTPException(
                status_code=422, detail=f"{label} cannot have more than two decimal places"
            )
    except InvalidOperation as exc:
        raise HTTPException(status_code=422, detail=f"{label} is invalid") from exc
    return value


def _optional_threshold(value: object, label: str) -> Decimal | None:
    if value is None:
        return None
    return _threshold(value, label)


def _validate_range(min_amount: Decimal, max_amount: Decimal | None) -> None:
    if max_amount is not None and max_amount < min_amount:
        raise HTTPException(
            status_code=422, detail="Maximum amount must be at least the minimum amount"
        )


def _role_id(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise HTTPException(status_code=422, detail="Choose an approver role")
    return value


def _snapshot(rule: ApprovalRule) -> dict[str, object]:
    return {
        "doc_type": rule.doc_type,
        "min_amount": str(rule.min_amount),
        "max_amount": str(rule.max_amount) if rule.max_amount is not None else None,
        "approver_role_id": rule.approver_role_id,
        "is_active": rule.is_active,
    }
