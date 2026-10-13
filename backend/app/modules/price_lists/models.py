from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

ID_TYPE = (
    BigInteger().with_variant(BIGINT(unsigned=True), "mysql").with_variant(Integer(), "sqlite")
)


class PriceList(Base):
    __tablename__ = "price_lists"
    __table_args__ = (
        Index("ix_price_lists_is_default", "is_default"),
        Index("ix_price_lists_valid_from", "valid_from"),
        Index("ix_price_lists_valid_to", "valid_to"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0")
    )
    valid_from: Mapped[date] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date] = mapped_column(Date, nullable=True)
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


class ProductPrice(Base):
    __tablename__ = "product_prices"
    __table_args__ = (
        UniqueConstraint("price_list_id", "product_id", name="uq_product_prices_list_product"),
        Index("ix_product_prices_price_list_id", "price_list_id"),
        Index("ix_product_prices_product_id", "product_id"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    price_list_id: Mapped[int] = mapped_column(
        ID_TYPE,
        ForeignKey("price_lists.id", ondelete="RESTRICT"),
        nullable=False,
    )
    product_id: Mapped[int] = mapped_column(
        ID_TYPE,
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )