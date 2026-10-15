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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

ID_TYPE = (
    BigInteger().with_variant(BIGINT(unsigned=True), "mysql").with_variant(Integer(), "sqlite")
)


class SupplierPayment(Base):
    __tablename__ = "supplier_payments"
    __table_args__ = (
        UniqueConstraint("doc_no", name="uq_supplier_payments_doc_no"),
        CheckConstraint("amount > 0", name="ck_supplier_payments_positive_amount"),
        CheckConstraint("status = 'POSTED'", name="ck_supplier_payments_posted_status"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    doc_no: Mapped[str] = mapped_column(String(50), nullable=False)
    doc_date: Mapped[date] = mapped_column(Date, nullable=False)
    supplier_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    account_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("money_accounts.id", ondelete="RESTRICT"), nullable=False, index=True
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
    allocations: Mapped[list["SupplierPaymentAllocation"]] = relationship(
        back_populates="payment",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="SupplierPaymentAllocation.id",
    )


class SupplierPaymentAllocation(Base):
    __tablename__ = "payment_allocations"
    __table_args__ = (
        CheckConstraint(
            "ref_type IN ('RECEIPT', 'DIRECT_PURCHASE')",
            name="ck_payment_allocations_ref_type",
        ),
        CheckConstraint("amount > 0", name="ck_payment_allocations_positive_amount"),
        UniqueConstraint("payment_id", "ref_type", "ref_id", name="uq_payment_allocations_source"),
        Index("ix_payment_allocations_source", "ref_type", "ref_id"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    payment_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("supplier_payments.id", ondelete="CASCADE"), nullable=False
    )
    ref_type: Mapped[str] = mapped_column(String(20), nullable=False)
    ref_id: Mapped[int] = mapped_column(ID_TYPE, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    payment: Mapped[SupplierPayment] = relationship(back_populates="allocations")
