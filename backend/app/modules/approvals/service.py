from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.approvals import repository
from app.modules.approvals.models import ApprovalAction, ApprovalRequest, ApprovalRule
from app.modules.auth.audit import record_audit
from app.modules.auth.models import User

SUPPORTED_DOCUMENT_TYPES = {"PURCHASE_ORDER", "EXPENSE", "STOCK_ADJUSTMENT"}


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


def request_approval_if_required(
    db: Session,
    *,
    doc_type: str,
    doc_id: int,
    amount: Decimal,
    actor: User,
    ip: str | None = None,
) -> ApprovalRequest | None:
    if not amount.is_finite() or amount < 0:
        raise HTTPException(status_code=422, detail="Approval amount must be nonnegative")
    evaluated_amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if evaluated_amount > Decimal("9999999999999999.99"):
        raise HTTPException(status_code=422, detail="Approval amount exceeds supported precision")
    rule = repository.get_matching_rule(db, doc_type, evaluated_amount)
    if rule is None:
        return None

    request = ApprovalRequest(
        doc_type=doc_type,
        doc_id=doc_id,
        amount=evaluated_amount,
        requested_by=actor.id,
        rule_id=rule.id,
        status="PENDING",
    )
    db.add(request)
    db.flush()
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="approval_request",
        entity_id=request.id,
        action="CREATE",
        after=_request_snapshot(request),
        ip=ip,
    )
    return request


def list_pending_requests(
    db: Session, actor: User, *, offset: int = 0, limit: int = 50
) -> list[dict[str, object]]:
    requests = repository.list_pending_for_user(db, actor.id, offset=offset, limit=limit)
    return [_request_details(db, item) for item in requests]


def decide_request(
    db: Session,
    request_id: int,
    *,
    action: str,
    note: str | None,
    actor: User,
    ip: str | None = None,
) -> dict[str, object]:
    try:
        request = repository.get_request(db, request_id, for_update=True)
        if request is None:
            raise HTTPException(status_code=404, detail="Approval request not found")
        if request.status != "PENDING":
            raise HTTPException(status_code=409, detail="Approval request is no longer pending")
        if request.requested_by == actor.id:
            raise HTTPException(
                status_code=403, detail="Requesters cannot approve their own document"
            )
        if not request.rule.approver_role.is_active or all(
            role.id != request.rule.approver_role_id or not role.is_active for role in actor.roles
        ):
            raise HTTPException(
                status_code=403, detail="Your account does not have the required approver role"
            )
        if action not in {"APPROVE", "REJECT"}:
            raise HTTPException(status_code=422, detail="Approval action is invalid")

        before = _request_snapshot(request)
        _apply_document_decision(db, request, action, actor, ip)
        request.status = "APPROVED" if action == "APPROVE" else "REJECTED"
        request.decided_at = datetime.now(UTC)
        db.add(
            ApprovalAction(
                request_id=request.id,
                user_id=actor.id,
                action=action,
                note=note.strip() if note and note.strip() else None,
            )
        )
        db.flush()
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="approval_request",
            entity_id=request.id,
            action="STATUS",
            before=before,
            after={**_request_snapshot(request), "action": action, "note": note},
            ip=ip,
        )
        db.commit()
        return _request_details(db, repository.get_request(db, request.id) or request)
    except Exception:
        db.rollback()
        raise


def _apply_document_decision(
    db: Session, request: ApprovalRequest, action: str, actor: User, ip: str | None
) -> None:
    status = "APPROVED" if action == "APPROVE" else "DRAFT"
    if request.doc_type == "PURCHASE_ORDER":
        from app.modules.purchase_orders.service import set_purchase_order_approval_status

        set_purchase_order_approval_status(db, request.doc_id, status=status, actor=actor, ip=ip)
    elif request.doc_type == "EXPENSE":
        from app.modules.expenses.service import decide_expense

        decide_expense(db, request.doc_id, approved=action == "APPROVE", actor=actor, ip=ip)
    elif request.doc_type == "STOCK_ADJUSTMENT":
        from app.modules.stock_adjustments.service import decide_adjustment

        decide_adjustment(
            db,
            request.doc_id,
            approved=action == "APPROVE",
            actor=actor,
            ip=ip,
        )
    else:
        raise HTTPException(status_code=409, detail="Document type is not supported for approval")


def _request_details(db: Session, request: ApprovalRequest) -> dict[str, object]:
    if request.doc_type == "PURCHASE_ORDER":
        from app.modules.purchase_orders import service as purchase_order_service

        purchase_order = purchase_order_service.get_purchase_order(db, request.doc_id)
        if purchase_order is None:
            raise RuntimeError(f"Approval request {request.id} refers to a missing document")
        doc_no = purchase_order.doc_no
        doc_status = purchase_order.status
    elif request.doc_type == "EXPENSE":
        from app.modules.expenses import service as expense_service

        expense = expense_service.get_expense(db, request.doc_id)
        if expense is None:
            raise RuntimeError(f"Approval request {request.id} refers to a missing document")
        doc_no = expense.doc_no
        doc_status = expense.status
    elif request.doc_type == "STOCK_ADJUSTMENT":
        from app.modules.stock_adjustments import service as adjustment_service

        adjustment = adjustment_service.get_adjustment(db, request.doc_id)
        if adjustment is None:
            raise RuntimeError(f"Approval request {request.id} refers to a missing document")
        doc_no = adjustment.doc_no
        doc_status = adjustment.status
    else:
        raise RuntimeError(f"Unsupported approval document type: {request.doc_type}")
    return {
        "id": request.id,
        "doc_type": request.doc_type,
        "doc_id": request.doc_id,
        "doc_no": doc_no,
        "doc_status": doc_status,
        "amount": request.amount,
        "requested_by": request.requested_by,
        "requester_name": request.requester.full_name,
        "approver_role_id": request.rule.approver_role_id,
        "approver_role_name": request.rule.approver_role.name,
        "requested_at": request.requested_at,
        "status": request.status,
    }


def _request_snapshot(request: ApprovalRequest) -> dict[str, object]:
    return {
        "doc_type": request.doc_type,
        "doc_id": request.doc_id,
        "amount": str(request.amount),
        "requested_by": request.requested_by,
        "rule_id": request.rule_id,
        "status": request.status,
        "decided_at": request.decided_at.isoformat() if request.decided_at else None,
    }


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
    if (
        len(normalized) > 50
        or not normalized[0].isalpha()
        or not all(char.isascii() and (char.isalnum() or char == "_") for char in normalized)
    ):
        raise HTTPException(status_code=422, detail="Document type format is invalid")
    if normalized not in SUPPORTED_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=(
                "Approval rules currently support purchase orders, expenses, "
                "and stock adjustments"
            ),
        )
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
