from datetime import date
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

ID_TYPE = (
    BigInteger().with_variant(BIGINT(unsigned=True), "mysql").with_variant(Integer(), "sqlite")
)


class StockAdjustment(Base):
    __tablename__ = "stock_adjustments"
    __table_args__ = (
        UniqueConstraint("doc_no", name="uq_stock_adjustments_doc_no"),
        CheckConstraint(
            "status IN ('DRAFT', 'PENDING_APPROVAL', 'POSTED')",
            name="ck_stock_adjustments_status",
        ),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    doc_no: Mapped[str] = mapped_column(String(50), nullable=False)
    doc_date: Mapped[date] = mapped_column(Date, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="POSTED")
    lines: Mapped[list["StockAdjustmentLine"]] = relationship(
        back_populates="adjustment", cascade="all, delete-orphan", lazy="selectin"
    )


class StockAdjustmentLine(Base):
    __tablename__ = "stock_adjustment_lines"
    __table_args__ = (
        CheckConstraint("qty_signed <> 0", name="ck_stock_adjustment_lines_nonzero_qty"),
        CheckConstraint("unit_cost >= 0", name="ck_stock_adjustment_lines_nonnegative_cost"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    adjustment_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("stock_adjustments.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    qty_signed: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    adjustment: Mapped[StockAdjustment] = relationship(back_populates="lines")
