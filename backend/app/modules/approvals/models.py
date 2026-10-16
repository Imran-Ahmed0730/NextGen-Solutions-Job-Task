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
    text,
)
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.modules.auth.models import Role

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
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("1")
    )
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
