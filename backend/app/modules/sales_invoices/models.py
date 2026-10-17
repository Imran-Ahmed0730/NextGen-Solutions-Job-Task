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
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.modules.products.models import Product
from app.modules.sales.models import SalesDelivery

ID_TYPE = (
    BigInteger().with_variant(BIGINT(unsigned=True), "mysql").with_variant(Integer(), "sqlite")
)


class SalesInvoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("doc_no", name="uq_invoices_doc_no"),
        UniqueConstraint("delivery_id", name="uq_invoices_delivery_id"),
        CheckConstraint("subtotal >= 0", name="ck_invoices_nonnegative_subtotal"),
        CheckConstraint("discount >= 0", name="ck_invoices_nonnegative_discount"),
        CheckConstraint("total >= 0", name="ck_invoices_nonnegative_total"),
        CheckConstraint("cogs_total >= 0", name="ck_invoices_nonnegative_cogs"),
        CheckConstraint("status = 'POSTED'", name="ck_invoices_posted_status"),
        Index("ix_invoices_doc_date", "doc_date"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    doc_no: Mapped[str] = mapped_column(String(50), nullable=False)
    doc_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    customer_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    delivery_id: Mapped[int] = mapped_column(
        ID_TYPE,
        ForeignKey("deliveries.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="POSTED")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    discount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    cogs_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    created_by: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    delivery: Mapped["SalesDelivery"] = relationship(back_populates="invoice")
    lines: Mapped[list["SalesInvoiceLine"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="SalesInvoiceLine.id",
    )


class SalesInvoiceLine(Base):
    __tablename__ = "invoice_lines"
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_invoice_lines_positive_qty"),
        CheckConstraint("unit_price >= 0", name="ck_invoice_lines_nonnegative_unit_price"),
        CheckConstraint("line_total >= 0", name="ck_invoice_lines_nonnegative_total"),
        CheckConstraint("unit_cost_cogs >= 0", name="ck_invoice_lines_nonnegative_cogs"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    unit_cost_cogs: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    invoice: Mapped[SalesInvoice] = relationship(back_populates="lines")
    product: Mapped[Product] = relationship(lazy="joined")
