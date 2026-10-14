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
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

ID_TYPE = (
    BigInteger().with_variant(BIGINT(unsigned=True), "mysql").with_variant(Integer(), "sqlite")
)


class StockTransfer(Base):
    __tablename__ = "stock_transfers"
    __table_args__ = (
        UniqueConstraint("doc_no", name="uq_stock_transfers_doc_no"),
        CheckConstraint(
            "from_warehouse_id <> to_warehouse_id",
            name="ck_stock_transfers_distinct_warehouses",
        ),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    doc_no: Mapped[str] = mapped_column(String(50), nullable=False)
    doc_date: Mapped[date] = mapped_column(Date, nullable=False)
    from_warehouse_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    to_warehouse_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="POSTED")
    note: Mapped[str] = mapped_column(Text, nullable=True)
    lines: Mapped[list["StockTransferLine"]] = relationship(
        back_populates="transfer", cascade="all, delete-orphan", lazy="selectin"
    )


class StockTransferLine(Base):
    __tablename__ = "stock_transfer_lines"
    __table_args__ = (CheckConstraint("qty > 0", name="ck_stock_transfer_lines_positive_qty"),)

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    transfer_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("stock_transfers.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    transfer: Mapped[StockTransfer] = relationship(back_populates="lines")
