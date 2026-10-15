import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.modules.sales.models import SalesOrderLine

ID_TYPE = (
    BigInteger().with_variant(BIGINT(unsigned=True), "mysql").with_variant(Integer(), "sqlite")
)


class MovementType(str, enum.Enum):
    PURCHASE_RECEIPT = "PURCHASE_RECEIPT"
    PURCHASE_RETURN = "PURCHASE_RETURN"
    PRODUCTION_CONSUME = "PRODUCTION_CONSUME"
    PRODUCTION_OUTPUT = "PRODUCTION_OUTPUT"
    SALE_DELIVERY = "SALE_DELIVERY"
    SALE_RETURN = "SALE_RETURN"
    TRANSFER_OUT = "TRANSFER_OUT"
    TRANSFER_IN = "TRANSFER_IN"
    ADJUSTMENT_IN = "ADJUSTMENT_IN"
    ADJUSTMENT_OUT = "ADJUSTMENT_OUT"
    COUNT_ADJUSTMENT = "COUNT_ADJUSTMENT"
    OPENING = "OPENING"


class StockTransaction(Base):
    __tablename__ = "stock_transactions"
    __table_args__ = (
        CheckConstraint("qty_signed <> 0", name="ck_stock_transactions_nonzero_qty"),
        Index(
            "ix_stock_transactions_product_warehouse_date",
            "product_id",
            "warehouse_id",
            "txn_date",
        ),
        Index("ix_stock_transactions_source", "source_type", "source_id"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    txn_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    product_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    movement_type: Mapped[MovementType] = mapped_column(
        Enum(
            MovementType,
            native_enum=False,
            length=30,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    qty_signed: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=True)
    source_id: Mapped[int] = mapped_column(ID_TYPE, nullable=True)
    source_line_id: Mapped[int] = mapped_column(ID_TYPE, nullable=True)
    note: Mapped[str] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class StockBalance(Base):
    __tablename__ = "stock_balances"
    __table_args__ = (
        CheckConstraint("qty_reserved >= 0", name="ck_stock_balances_reserved_nonnegative"),
        Index("ix_stock_balances_warehouse_product", "warehouse_id", "product_id"),
    )

    product_id: Mapped[int] = mapped_column(
        ID_TYPE,
        ForeignKey("products.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    warehouse_id: Mapped[int] = mapped_column(
        ID_TYPE,
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    qty_on_hand: Mapped[Decimal] = mapped_column(
        Numeric(18, 3), nullable=False, default=Decimal("0.000"), server_default=text("0.000")
    )
    qty_reserved: Mapped[Decimal] = mapped_column(
        Numeric(18, 3), nullable=False, default=Decimal("0.000"), server_default=text("0.000")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )

    @property
    def available(self) -> Decimal:
        return self.qty_on_hand - self.qty_reserved


class StockReservation(Base):
    __tablename__ = "stock_reservations"
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_stock_reservations_positive_qty"),
        CheckConstraint(
            "qty_consumed >= 0 AND qty_released >= 0 AND qty_consumed + qty_released <= qty",
            name="ck_stock_reservations_quantities_within_total",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'RELEASED', 'CONSUMED')",
            name="ck_stock_reservations_status",
        ),
        Index("ix_stock_reservations_sales_order_line_id", "sales_order_line_id"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    sales_order_line_id: Mapped[int] = mapped_column(
        ID_TYPE,
        ForeignKey("sales_order_lines.id", ondelete="RESTRICT"),
        nullable=False,
    )
    product_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    qty_consumed: Mapped[Decimal] = mapped_column(
        Numeric(18, 3), nullable=False, default=Decimal("0.000"), server_default=text("0.000")
    )
    qty_released: Mapped[Decimal] = mapped_column(
        Numeric(18, 3), nullable=False, default=Decimal("0.000"), server_default=text("0.000")
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ACTIVE", server_default="ACTIVE"
    )
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
    sales_order_line: Mapped["SalesOrderLine"] = relationship(back_populates="reservations")
