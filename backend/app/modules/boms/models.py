from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
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
from app.modules.products.models import Product

ID_TYPE = (
    BigInteger().with_variant(BIGINT(unsigned=True), "mysql").with_variant(Integer(), "sqlite")
)


class BOM(Base):
    __tablename__ = "boms"
    __table_args__ = (
        UniqueConstraint("code", name="uq_boms_code"),
        CheckConstraint("output_qty > 0", name="ck_boms_positive_output_qty"),
        CheckConstraint("labor_cost_default >= 0", name="ck_boms_nonnegative_labor"),
        CheckConstraint("overhead_cost_default >= 0", name="ck_boms_nonnegative_overhead"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    finished_product_id: Mapped[int] = mapped_column(
        ID_TYPE,
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    output_qty: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    labor_cost_default: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00"), server_default=text("0.00")
    )
    overhead_cost_default: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00"), server_default=text("0.00")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("1")
    )
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )

    finished_product: Mapped[Product] = relationship(foreign_keys=[finished_product_id])
    lines: Mapped[list["BOMLine"]] = relationship(
        back_populates="bom",
        cascade="all, delete-orphan",
        order_by="BOMLine.id",
        lazy="selectin",
    )


class BOMLine(Base):
    __tablename__ = "bom_lines"
    __table_args__ = (
        UniqueConstraint("bom_id", "raw_product_id", name="uq_bom_lines_component"),
        CheckConstraint("qty > 0", name="ck_bom_lines_positive_qty"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    bom_id: Mapped[int] = mapped_column(
        ID_TYPE,
        ForeignKey("boms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    raw_product_id: Mapped[int] = mapped_column(
        ID_TYPE,
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)

    bom: Mapped[BOM] = relationship(back_populates="lines")
    raw_product: Mapped[Product] = relationship(foreign_keys=[raw_product_id])
