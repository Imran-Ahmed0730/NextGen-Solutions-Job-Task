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

ID_TYPE = (
    BigInteger().with_variant(BIGINT(unsigned=True), "mysql").with_variant(Integer(), "sqlite")
)


class GoodsReceipt(Base):
    __tablename__ = "goods_receipts"
    __table_args__ = (
        UniqueConstraint("doc_no", name="uq_goods_receipts_doc_no"),
        CheckConstraint("status = 'POSTED'", name="ck_goods_receipts_posted_status"),
        CheckConstraint("total >= 0", name="ck_goods_receipts_nonnegative_total"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    doc_no: Mapped[str] = mapped_column(String(50), nullable=False)
    doc_date: Mapped[date] = mapped_column(Date, nullable=False)
    po_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("purchase_orders.id", ondelete="RESTRICT"), nullable=False
    )
    supplier_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True
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
    lines: Mapped[list["GoodsReceiptLine"]] = relationship(
        back_populates="receipt",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="GoodsReceiptLine.id",
    )


class GoodsReceiptLine(Base):
    __tablename__ = "goods_receipt_lines"
    __table_args__ = (
        UniqueConstraint("receipt_id", "po_line_id", name="uq_goods_receipt_lines_po_line"),
        CheckConstraint("qty > 0", name="ck_goods_receipt_lines_positive_qty"),
        CheckConstraint("unit_cost >= 0", name="ck_goods_receipt_lines_nonnegative_unit_cost"),
        CheckConstraint("line_total >= 0", name="ck_goods_receipt_lines_nonnegative_total"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    receipt_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("goods_receipts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    po_line_id: Mapped[int] = mapped_column(
        ID_TYPE,
        ForeignKey("purchase_order_lines.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    receipt: Mapped[GoodsReceipt] = relationship(back_populates="lines")
    product: Mapped[Product] = relationship(lazy="joined")

    @property
    def product_sku(self) -> str:
        return self.product.sku

    @property
    def product_name(self) -> str:
        return self.product.name
