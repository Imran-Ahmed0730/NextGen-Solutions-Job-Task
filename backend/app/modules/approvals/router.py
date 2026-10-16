from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.approvals import service
from app.modules.approvals.models import ApprovalRule
from app.modules.approvals.schemas import (
    ApprovalRoleOption,
    ApprovalRuleCreate,
    ApprovalRuleResponse,
    ApprovalRuleUpdate,
)
from app.modules.auth.models import User

router = APIRouter(prefix="/api/v1/approvals/rules", tags=["approvals"])


@router.get("", response_model=list[ApprovalRuleResponse])
def list_approval_rules(
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("approvals.rules.read")),
) -> list[ApprovalRule]:
    return service.list_rules(db, include_inactive=include_inactive)


@router.get("/options/roles", response_model=list[ApprovalRoleOption])
def list_approver_roles(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("approvals.rules.read")),
) -> list[dict[str, object]]:
    return service.list_active_roles(db)


@router.post("", response_model=ApprovalRuleResponse, status_code=status.HTTP_201_CREATED)
def create_approval_rule(
    payload: ApprovalRuleCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("approvals.rules.create")),
) -> ApprovalRule:
    return service.create_rule(db, payload.model_dump(), actor, _ip(request))


@router.patch("/{rule_id}", response_model=ApprovalRuleResponse)
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


@router.post("/{rule_id}/activate", response_model=ApprovalRuleResponse)
def activate_approval_rule(
    rule_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("approvals.rules.update")),
) -> ApprovalRule:
    return service.set_rule_active(db, rule_id, True, actor, _ip(request))


@router.post("/{rule_id}/deactivate", response_model=ApprovalRuleResponse)
def deactivate_approval_rule(
    rule_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("approvals.rules.update")),
) -> ApprovalRule:
    return service.set_rule_active(db, rule_id, False, actor, _ip(request))


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None
