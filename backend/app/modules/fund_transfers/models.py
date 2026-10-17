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


class FundTransfer(Base):
    __tablename__ = "fund_transfers"
    __table_args__ = (
        UniqueConstraint("doc_no", name="uq_fund_transfers_doc_no"),
        CheckConstraint("amount > 0", name="ck_fund_transfers_positive_amount"),
        CheckConstraint("status = 'POSTED'", name="ck_fund_transfers_posted_status"),
        CheckConstraint(
            "from_account_id <> to_account_id", name="ck_fund_transfers_different_accounts"
        ),
        Index("ix_fund_transfers_from_account", "from_account_id"),
        Index("ix_fund_transfers_to_account", "to_account_id"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    doc_no: Mapped[str] = mapped_column(String(50), nullable=False)
    doc_date: Mapped[date] = mapped_column(Date, nullable=False)
    from_account_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("money_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    to_account_id: Mapped[int] = mapped_column(
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
