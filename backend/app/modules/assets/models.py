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


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("asset_code", name="uq_assets_asset_code"),
        CheckConstraint(
            "status IN ('IN_USE', 'IN_STORE', 'UNDER_MAINTENANCE', 'DISPOSED')",
            name="ck_assets_status",
        ),
        CheckConstraint("purchase_cost >= 0", name="ck_assets_purchase_cost_nonnegative"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    asset_code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    purchase_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    location: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="IN_STORE")
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("1"))
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
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
    assignments: Mapped[list["AssetAssignment"]] = relationship(
        back_populates="asset", lazy="selectin", order_by="AssetAssignment.id"
    )
    maintenance: Mapped[list["AssetMaintenance"]] = relationship(
        back_populates="asset", lazy="selectin", order_by="AssetMaintenance.id"
    )


class AssetAssignment(Base):
    __tablename__ = "asset_assignments"
    __table_args__ = (
        CheckConstraint(
            "returned_on IS NULL OR returned_on >= assigned_on",
            name="ck_asset_assignments_return_date",
        ),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    location: Mapped[str] = mapped_column(String(150), nullable=False)
    assigned_on: Mapped[date] = mapped_column(Date, nullable=False)
    returned_on: Mapped[date] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    asset: Mapped[Asset] = relationship(back_populates="assignments")


class AssetMaintenance(Base):
    __tablename__ = "asset_maintenance"
    __table_args__ = (
        CheckConstraint("cost >= 0", name="ck_asset_maintenance_cost_nonnegative"),
        CheckConstraint(
            "next_due_date IS NULL OR next_due_date >= maintenance_date",
            name="ck_asset_maintenance_next_due_date",
        ),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    maintenance_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    next_due_date: Mapped[date] = mapped_column(Date, nullable=True)
    created_by: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    asset: Mapped[Asset] = relationship(back_populates="maintenance")
