from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

ID_TYPE = (
    BigInteger().with_variant(BIGINT(unsigned=True), "mysql").with_variant(Integer(), "sqlite")
)


class Income(Base):
    __tablename__ = "incomes"
    __table_args__ = (
        UniqueConstraint("doc_no", name="uq_incomes_doc_no"),
        CheckConstraint("amount > 0", name="ck_incomes_positive_amount"),
        CheckConstraint("status = 'POSTED'", name="ck_incomes_posted_status"),
        Index("ix_incomes_category_id", "category_id"),
        Index("ix_incomes_account_id", "account_id"),
        Index("ix_incomes_doc_date", "doc_date"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    doc_no: Mapped[str] = mapped_column(String(50), nullable=False)
    doc_date: Mapped[date] = mapped_column(Date, nullable=False)
    category_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("income_categories.id", ondelete="RESTRICT"), nullable=False
    )
    account_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("money_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="POSTED")
    note: Mapped[str] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
