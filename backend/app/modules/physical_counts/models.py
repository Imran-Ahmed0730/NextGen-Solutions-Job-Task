from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

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

ID_TYPE = (
    BigInteger().with_variant(BIGINT(unsigned=True), "mysql").with_variant(Integer(), "sqlite")
)

if TYPE_CHECKING:
    from app.modules.products.models import Product


class PhysicalCount(Base):
    __tablename__ = "physical_counts"
    __table_args__ = (
        UniqueConstraint("doc_no", name="uq_physical_counts_doc_no"),
        CheckConstraint(
            "status IN ('OPEN', 'COUNTED', 'POSTED')",
            name="ck_physical_counts_status",
        ),
        CheckConstraint(
            "(status = 'POSTED' AND doc_no IS NOT NULL AND posted_at IS NOT NULL) "
            "OR (status IN ('OPEN', 'COUNTED') AND doc_no IS NULL AND posted_at IS NULL)",
            name="ck_physical_counts_posting_fields",
        ),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    doc_no: Mapped[str] = mapped_column(String(50), nullable=True)
    count_date: Mapped[date] = mapped_column(Date, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")
    created_by: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    posted_by: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )
    lines: Mapped[list["PhysicalCountLine"]] = relationship(
        back_populates="physical_count",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class PhysicalCountLine(Base):
    __tablename__ = "physical_count_lines"
    __table_args__ = (
        UniqueConstraint("count_id", "product_id", name="uq_physical_count_lines_count_product"),
        CheckConstraint("system_qty >= 0", name="ck_physical_count_lines_system_qty_nonnegative"),
        CheckConstraint(
            "counted_qty IS NULL OR counted_qty >= 0",
            name="ck_physical_count_lines_counted_qty_nonnegative",
        ),
        CheckConstraint(
            "(counted_qty IS NULL AND variance_qty IS NULL) "
            "OR (counted_qty IS NOT NULL AND variance_qty IS NOT NULL)",
            name="ck_physical_count_lines_count_and_variance",
        ),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    count_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("physical_counts.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    system_qty: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    counted_qty: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=True)
    variance_qty: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=True)
    physical_count: Mapped[PhysicalCount] = relationship(back_populates="lines")
    product: Mapped["Product"] = relationship(lazy="joined")

    @property
    def product_sku(self) -> str:
        return self.product.sku

    @property
    def product_name(self) -> str:
        return self.product.name

    @property
    def unit_code(self) -> str:
        return self.product.unit.code
