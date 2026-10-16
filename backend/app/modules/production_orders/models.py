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
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.modules.boms.models import BOM

ID_TYPE = (
    BigInteger().with_variant(BIGINT(unsigned=True), "mysql").with_variant(Integer(), "sqlite")
)


class ProductionOrder(Base):
    __tablename__ = "production_orders"
    __table_args__ = (
        UniqueConstraint("doc_no", name="uq_production_orders_doc_no"),
        CheckConstraint(
            "status IN ('DRAFT', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')",
            name="ck_production_orders_status",
        ),
        CheckConstraint("planned_qty > 0", name="ck_production_orders_positive_planned_qty"),
        CheckConstraint(
            "actual_qty IS NULL OR actual_qty > 0",
            name="ck_production_orders_positive_actual_qty",
        ),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    doc_no: Mapped[str] = mapped_column(String(50), nullable=False)
    doc_date: Mapped[date] = mapped_column(Date, nullable=False)
    bom_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("boms.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    finished_product_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    planned_qty: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    actual_qty: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=True)
    warehouse_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="DRAFT")
    labor_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=True)
    overhead_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=True)
    material_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=True)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=True)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
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

    bom: Mapped[BOM] = relationship()
    consumption: Mapped[list["ProductionConsumption"]] = relationship(
        back_populates="production_order",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ProductionConsumption.id",
    )
    outputs: Mapped[list["ProductionOutput"]] = relationship(
        back_populates="production_order",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ProductionOutput.id",
    )


class ProductionConsumption(Base):
    __tablename__ = "production_consumption"
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_production_consumption_positive_qty"),
        CheckConstraint("unit_cost >= 0", name="ck_production_consumption_nonnegative_unit_cost"),
        CheckConstraint("line_cost >= 0", name="ck_production_consumption_nonnegative_line_cost"),
        UniqueConstraint(
            "production_order_id", "product_id", name="uq_production_consumption_product"
        ),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    production_order_id: Mapped[int] = mapped_column(
        ID_TYPE,
        ForeignKey("production_orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    line_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    production_order: Mapped[ProductionOrder] = relationship(back_populates="consumption")


class ProductionOutput(Base):
    __tablename__ = "production_outputs"
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_production_outputs_positive_qty"),
        CheckConstraint("unit_cost >= 0", name="ck_production_outputs_nonnegative_unit_cost"),
        UniqueConstraint("production_order_id", name="uq_production_outputs_order"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    production_order_id: Mapped[int] = mapped_column(
        ID_TYPE,
        ForeignKey("production_orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    production_order: Mapped[ProductionOrder] = relationship(back_populates="outputs")
