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


class Quotation(Base):
    __tablename__ = "quotations"
    __table_args__ = (
        UniqueConstraint("doc_no", name="uq_quotations_doc_no"),
        CheckConstraint("subtotal >= 0", name="ck_quotations_nonnegative_subtotal"),
        CheckConstraint("discount >= 0", name="ck_quotations_nonnegative_discount"),
        CheckConstraint("total >= 0", name="ck_quotations_nonnegative_total"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    doc_no: Mapped[str] = mapped_column(String(50), nullable=False)
    doc_date: Mapped[date] = mapped_column(Date, nullable=False)
    customer_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    valid_until: Mapped[date] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="DRAFT")
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
    lines: Mapped[list["QuotationLine"]] = relationship(
        back_populates="quotation",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="QuotationLine.id",
    )


class QuotationLine(Base):
    __tablename__ = "quotation_lines"
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_quotation_lines_positive_qty"),
        CheckConstraint("unit_price >= 0", name="ck_quotation_lines_nonnegative_unit_price"),
        CheckConstraint("line_total >= 0", name="ck_quotation_lines_nonnegative_total"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    quotation_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("quotations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    quotation: Mapped[Quotation] = relationship(back_populates="lines")
