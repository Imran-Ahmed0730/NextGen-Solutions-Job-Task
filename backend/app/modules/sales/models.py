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

ID_TYPE = (
    BigInteger().with_variant(BIGINT(unsigned=True), "mysql").with_variant(Integer(), "sqlite")
)


class SalesOrder(Base):
    __tablename__ = "sales_orders"
    __table_args__ = (
        UniqueConstraint("doc_no", name="uq_sales_orders_doc_no"),
        CheckConstraint("subtotal >= 0", name="ck_sales_orders_nonnegative_subtotal"),
        CheckConstraint("discount >= 0", name="ck_sales_orders_nonnegative_discount"),
        CheckConstraint("total >= 0", name="ck_sales_orders_nonnegative_total"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    doc_no: Mapped[str] = mapped_column(String(50), nullable=False)
    doc_date: Mapped[date] = mapped_column(Date, nullable=False)
    customer_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    quotation_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("quotations.id", ondelete="RESTRICT"), nullable=True
    )
    warehouse_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="DRAFT")
    delivery_date: Mapped[date] = mapped_column(Date, nullable=True)
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, server_default=text("0.00")
    )
    discount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, server_default=text("0.00")
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, server_default=text("0.00")
    )
    note: Mapped[str] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
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
    lines: Mapped[list["SalesOrderLine"]] = relationship(
        back_populates="sales_order",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="SalesOrderLine.id",
    )


class SalesOrderLine(Base):
    __tablename__ = "sales_order_lines"
    __table_args__ = (
        CheckConstraint("qty_ordered > 0", name="ck_sales_order_lines_positive_ordered_qty"),
        CheckConstraint("qty_reserved >= 0", name="ck_sales_order_lines_nonnegative_reserved_qty"),
        CheckConstraint("qty_produced >= 0", name="ck_sales_order_lines_nonnegative_produced_qty"),
        CheckConstraint(
            "qty_delivered >= 0", name="ck_sales_order_lines_nonnegative_delivered_qty"
        ),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("sales_orders.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    qty_ordered: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    qty_reserved: Mapped[Decimal] = mapped_column(
        Numeric(18, 3), nullable=False, server_default=text("0.000")
    )
    qty_produced: Mapped[Decimal] = mapped_column(
        Numeric(18, 3), nullable=False, server_default=text("0.000")
    )
    qty_delivered: Mapped[Decimal] = mapped_column(
        Numeric(18, 3), nullable=False, server_default=text("0.000")
    )
    sales_order: Mapped[SalesOrder] = relationship(back_populates="lines")
