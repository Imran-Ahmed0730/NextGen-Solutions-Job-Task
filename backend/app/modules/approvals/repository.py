from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.modules.approvals.models import ApprovalRule
from app.modules.auth.models import Role


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
        db.scalars(
            select(Role).where(Role.is_active.is_(True)).order_by(Role.name, Role.id)
        )
    )
