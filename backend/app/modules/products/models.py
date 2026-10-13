import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
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
from app.modules.product_categories.models import ProductCategory
from app.modules.units.models import Unit

ID_TYPE = (
    BigInteger().with_variant(BIGINT(unsigned=True), "mysql").with_variant(Integer(), "sqlite")
)


class ProductType(str, enum.Enum):
    RAW = "RAW"
    FINISHED = "FINISHED"
    TRADING = "TRADING"


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("sku", name="uq_products_sku"),
        Index("ix_products_category_id", "category_id"),
        Index("ix_products_unit_id", "unit_id"),
        Index("ix_products_type", "type"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[ProductType] = mapped_column(
        Enum(ProductType, native_enum=False, length=20), nullable=False
    )
    category_id: Mapped[int] = mapped_column(
        ID_TYPE,
        ForeignKey("product_categories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    unit_id: Mapped[int] = mapped_column(
        ID_TYPE,
        ForeignKey("units.id", ondelete="RESTRICT"),
        nullable=False,
    )
    is_stocked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("1")
    )
    reorder_level: Mapped[Decimal] = mapped_column(
        Numeric(18, 3), nullable=False, default=Decimal("0.000"), server_default=text("0.000")
    )
    avg_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000"), server_default=text("0.0000")
    )
    sales_price_default: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00"), server_default=text("0.00")
    )
    description: Mapped[str] = mapped_column(Text, nullable=True)
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

    category: Mapped[ProductCategory] = relationship("ProductCategory", lazy="joined")
    unit: Mapped[Unit] = relationship("Unit", lazy="joined")
