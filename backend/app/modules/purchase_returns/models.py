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
from app.modules.goods_receipts.models import GoodsReceipt
from app.modules.products.models import Product

ID_TYPE = (
    BigInteger().with_variant(BIGINT(unsigned=True), "mysql").with_variant(Integer(), "sqlite")
)


class PurchaseReturn(Base):
    __tablename__ = "purchase_returns"
    __table_args__ = (
        UniqueConstraint("doc_no", name="uq_purchase_returns_doc_no"),
        CheckConstraint("status = 'POSTED'", name="ck_purchase_returns_posted_status"),
        CheckConstraint("total >= 0", name="ck_purchase_returns_nonnegative_total"),
        Index("ix_purchase_returns_doc_date", "doc_date"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    doc_no: Mapped[str] = mapped_column(String(50), nullable=False)
    doc_date: Mapped[date] = mapped_column(Date, nullable=False)
    receipt_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("goods_receipts.id", ondelete="RESTRICT"), nullable=False
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
    lines: Mapped[list["PurchaseReturnLine"]] = relationship(
        back_populates="purchase_return",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="PurchaseReturnLine.id",
    )
    receipt: Mapped[GoodsReceipt] = relationship(lazy="joined")

    @property
    def receipt_doc_no(self) -> str:
        return self.receipt.doc_no


class PurchaseReturnLine(Base):
    __tablename__ = "purchase_return_lines"
    __table_args__ = (
        UniqueConstraint("return_id", "receipt_line_id", name="uq_purchase_return_lines_source"),
        CheckConstraint("qty > 0", name="ck_purchase_return_lines_positive_qty"),
        CheckConstraint("unit_cost >= 0", name="ck_purchase_return_lines_nonnegative_unit_cost"),
        CheckConstraint("line_total >= 0", name="ck_purchase_return_lines_nonnegative_total"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    return_id: Mapped[int] = mapped_column(
        ID_TYPE,
        ForeignKey("purchase_returns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    receipt_line_id: Mapped[int] = mapped_column(
        ID_TYPE,
        ForeignKey("goods_receipt_lines.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    purchase_return: Mapped[PurchaseReturn] = relationship(back_populates="lines")
    product: Mapped[Product] = relationship(lazy="joined")

    @property
    def product_sku(self) -> str:
        return self.product.sku

    @property
    def product_name(self) -> str:
        return self.product.name
