from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
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
from app.modules.products.models import Product
from app.modules.sales_invoices.models import SalesInvoice, SalesInvoiceLine

ID_TYPE = (
    BigInteger().with_variant(BIGINT(unsigned=True), "mysql").with_variant(Integer(), "sqlite")
)


class SalesReturn(Base):
    __tablename__ = "sales_returns"
    __table_args__ = (
        UniqueConstraint("doc_no", name="uq_sales_returns_doc_no"),
        CheckConstraint("status = 'POSTED'", name="ck_sales_returns_posted_status"),
        CheckConstraint("total >= 0", name="ck_sales_returns_nonnegative_total"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    doc_no: Mapped[str] = mapped_column(String(50), nullable=False)
    doc_date: Mapped[date] = mapped_column(Date, nullable=False)
    invoice_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    customer_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    warehouse_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="POSTED")
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    invoice: Mapped[SalesInvoice] = relationship(lazy="joined")
    lines: Mapped[list["SalesReturnLine"]] = relationship(
        back_populates="sales_return",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="SalesReturnLine.id",
    )

    @property
    def invoice_doc_no(self) -> str:
        return self.invoice.doc_no


class SalesReturnLine(Base):
    __tablename__ = "sales_return_lines"
    __table_args__ = (
        UniqueConstraint("return_id", "invoice_line_id", name="uq_sales_return_lines_source"),
        CheckConstraint("qty > 0", name="ck_sales_return_lines_positive_qty"),
        CheckConstraint("unit_price >= 0", name="ck_sales_return_lines_nonnegative_unit_price"),
        CheckConstraint("line_total >= 0", name="ck_sales_return_lines_nonnegative_total"),
        CheckConstraint("unit_cost_cogs >= 0", name="ck_sales_return_lines_nonnegative_cogs"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    return_id: Mapped[int] = mapped_column(
        ID_TYPE,
        ForeignKey("sales_returns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invoice_line_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("invoice_lines.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    unit_cost_cogs: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    sales_return: Mapped[SalesReturn] = relationship(back_populates="lines")
    product: Mapped[Product] = relationship(lazy="joined")
    invoice_line: Mapped[SalesInvoiceLine] = relationship(lazy="joined")

    @property
    def product_sku(self) -> str:
        return self.product.sku

    @property
    def product_name(self) -> str:
        return self.product.name

    @property
    def unit_code(self) -> str:
        return self.product.unit.code
