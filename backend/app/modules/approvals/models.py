from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.modules.auth.models import Role, User

ID_TYPE = (
    BigInteger().with_variant(BIGINT(unsigned=True), "mysql").with_variant(Integer(), "sqlite")
)


class ApprovalRule(Base):
    __tablename__ = "approval_rules"
    __table_args__ = (
        CheckConstraint("min_amount >= 0", name="ck_approval_rules_min_nonnegative"),
        CheckConstraint(
            "max_amount IS NULL OR max_amount >= min_amount",
            name="ck_approval_rules_max_gte_min",
        ),
        Index("ix_approval_rules_document_type", "doc_type"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False)
    min_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    max_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=True)
    approver_role_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )
    approver_role: Mapped[Role] = relationship(lazy="joined")


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED')",
            name="ck_approval_requests_status",
        ),
        CheckConstraint("amount >= 0", name="ck_approval_requests_amount_nonnegative"),
        Index("ix_approval_requests_document", "doc_type", "doc_id"),
        Index("ix_approval_requests_status_requested", "status", "requested_at"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False)
    doc_id: Mapped[int] = mapped_column(ID_TYPE, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    requested_by: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    rule_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("approval_rules.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="PENDING")
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    rule: Mapped[ApprovalRule] = relationship(lazy="joined")
    requester: Mapped["User"] = relationship(foreign_keys=[requested_by], lazy="joined")


class ApprovalAction(Base):
    __tablename__ = "approval_actions"
    __table_args__ = (
        CheckConstraint(
            "action IN ('APPROVE', 'REJECT')",
            name="ck_approval_actions_action",
        ),
        Index("ix_approval_actions_request", "request_id", "acted_at"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("approval_requests.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(10), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=True)
    acted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    request: Mapped[ApprovalRequest] = relationship()
    user: Mapped["User"] = relationship(foreign_keys=[user_id], lazy="joined")
