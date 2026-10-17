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


class CustomerCollection(Base):
    __tablename__ = "customer_collections"
    __table_args__ = (
        UniqueConstraint("doc_no", name="uq_customer_collections_doc_no"),
        CheckConstraint("amount > 0", name="ck_customer_collections_positive_amount"),
        CheckConstraint("status = 'POSTED'", name="ck_customer_collections_posted_status"),
        Index("ix_customer_collections_doc_date", "doc_date"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    doc_no: Mapped[str] = mapped_column(String(50), nullable=False)
    doc_date: Mapped[date] = mapped_column(Date, nullable=False)
    customer_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    account_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("money_accounts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    method_ref: Mapped[str] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="POSTED")
    note: Mapped[str] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
