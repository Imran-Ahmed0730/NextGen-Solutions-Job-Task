from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.approvals import service
from app.modules.approvals.models import ApprovalRule
from app.modules.approvals.schemas import (
    ApprovalDecision,
    ApprovalRequestResponse,
    ApprovalRoleOption,
    ApprovalRuleCreate,
    ApprovalRuleResponse,
    ApprovalRuleUpdate,
)
from app.modules.auth.models import User

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])


@router.get("/rules", response_model=list[ApprovalRuleResponse])
def list_approval_rules(
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("approvals.rules.read")),
) -> list[ApprovalRule]:
    return service.list_rules(db, include_inactive=include_inactive)


@router.get("/rules/options/roles", response_model=list[ApprovalRoleOption])
def list_approver_roles(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("approvals.rules.read")),
) -> list[dict[str, object]]:
    return service.list_active_roles(db)


@router.post("/rules", response_model=ApprovalRuleResponse, status_code=status.HTTP_201_CREATED)
def create_approval_rule(
    payload: ApprovalRuleCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("approvals.rules.create")),
) -> ApprovalRule:
    return service.create_rule(db, payload.model_dump(), actor, _ip(request))


@router.patch("/rules/{rule_id}", response_model=ApprovalRuleResponse)
def update_approval_rule(
    rule_id: int,
    payload: ApprovalRuleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("approvals.rules.update")),
) -> ApprovalRule:
    return service.update_rule(
        db, rule_id, payload.model_dump(exclude_unset=True), actor, _ip(request)
    )


@router.post("/rules/{rule_id}/activate", response_model=ApprovalRuleResponse)
def activate_approval_rule(
    rule_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("approvals.rules.update")),
) -> ApprovalRule:
    return service.set_rule_active(db, rule_id, True, actor, _ip(request))


@router.post("/rules/{rule_id}/deactivate", response_model=ApprovalRuleResponse)
def deactivate_approval_rule(
    rule_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("approvals.rules.update")),
) -> ApprovalRule:
    return service.set_rule_active(db, rule_id, False, actor, _ip(request))


@router.get("/requests", response_model=list[ApprovalRequestResponse])
def list_pending_approval_requests(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("approvals.requests.read")),
) -> list[dict[str, object]]:
    return service.list_pending_requests(db, actor, offset=offset, limit=limit)


@router.post("/requests/{request_id}/approve", response_model=ApprovalRequestResponse)
def approve_request(
    request_id: int,
    payload: ApprovalDecision,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("approvals.requests.decide")),
) -> dict[str, object]:
    return service.decide_request(
        db,
        request_id,
        action="APPROVE",
        note=payload.note,
        actor=actor,
        ip=_ip(request),
    )


@router.post("/requests/{request_id}/reject", response_model=ApprovalRequestResponse)
def reject_request(
    request_id: int,
    payload: ApprovalDecision,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("approvals.requests.decide")),
) -> dict[str, object]:
    return service.decide_request(
        db,
        request_id,
        action="REJECT",
        note=payload.note,
        actor=actor,
        ip=_ip(request),
    )


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None
