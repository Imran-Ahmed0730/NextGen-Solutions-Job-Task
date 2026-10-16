from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.modules.approvals.models import ApprovalRequest, ApprovalRule
from app.modules.auth.models import Role, user_roles


def list_rules(db: Session, *, include_inactive: bool) -> list[ApprovalRule]:
    statement = select(ApprovalRule).options(joinedload(ApprovalRule.approver_role))
    if not include_inactive:
        statement = statement.where(ApprovalRule.is_active.is_(True))
    return list(db.scalars(statement.order_by(ApprovalRule.doc_type, ApprovalRule.min_amount)))


def get_rule(db: Session, rule_id: int, *, for_update: bool = False) -> ApprovalRule | None:
    statement = (
        select(ApprovalRule)
        .options(joinedload(ApprovalRule.approver_role))
        .where(ApprovalRule.id == rule_id)
    )
    if for_update:
        statement = statement.with_for_update()
    return db.scalar(statement)


def list_doc_type_rules_for_update(db: Session, doc_type: str) -> list[ApprovalRule]:
    statement = (
        select(ApprovalRule)
        .where(ApprovalRule.doc_type == doc_type, ApprovalRule.is_active.is_(True))
        .order_by(ApprovalRule.min_amount, ApprovalRule.id)
        .with_for_update()
    )
    return list(db.scalars(statement))


def get_active_role(db: Session, role_id: int, *, for_update: bool = False) -> Role | None:
    statement = select(Role).where(Role.id == role_id, Role.is_active.is_(True))
    if for_update:
        statement = statement.with_for_update()
    return db.scalar(statement)


def list_active_roles(db: Session) -> list[Role]:
    return list(
        db.scalars(select(Role).where(Role.is_active.is_(True)).order_by(Role.name, Role.id))
    )


def get_matching_rule(db: Session, doc_type: str, amount: Decimal) -> ApprovalRule | None:
    return db.scalar(
        select(ApprovalRule)
        .where(
            ApprovalRule.doc_type == doc_type,
            ApprovalRule.is_active.is_(True),
            ApprovalRule.min_amount <= amount,
            (ApprovalRule.max_amount.is_(None) | (ApprovalRule.max_amount >= amount)),
        )
        .order_by(ApprovalRule.id)
    )


def get_request(
    db: Session, request_id: int, *, for_update: bool = False
) -> ApprovalRequest | None:
    statement = (
        select(ApprovalRequest)
        .options(
            joinedload(ApprovalRequest.rule),
            joinedload(ApprovalRequest.requester),
        )
        .where(ApprovalRequest.id == request_id)
    )
    if for_update:
        statement = statement.with_for_update()
    return db.scalar(statement)


def list_pending_for_user(
    db: Session, user_id: int, *, offset: int = 0, limit: int = 50
) -> list[ApprovalRequest]:
    statement = (
        select(ApprovalRequest)
        .join(ApprovalRule, ApprovalRequest.rule_id == ApprovalRule.id)
        .join(Role, Role.id == ApprovalRule.approver_role_id)
        .join(user_roles, user_roles.c.role_id == ApprovalRule.approver_role_id)
        .options(
            joinedload(ApprovalRequest.rule),
            joinedload(ApprovalRequest.requester),
        )
        .where(
            ApprovalRequest.status == "PENDING",
            Role.is_active.is_(True),
            user_roles.c.user_id == user_id,
            ApprovalRequest.requested_by != user_id,
        )
        .order_by(ApprovalRequest.requested_at, ApprovalRequest.id)
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(statement).unique())
