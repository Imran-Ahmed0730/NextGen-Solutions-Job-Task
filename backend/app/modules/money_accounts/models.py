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
    text,
)
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

ID_TYPE = (
    BigInteger().with_variant(BIGINT(unsigned=True), "mysql").with_variant(Integer(), "sqlite")
)


class MoneyAccountType(str, enum.Enum):
    CASH = "CASH"
    BANK = "BANK"
    MFS = "MFS"


class MoneyAccount(Base):
    __tablename__ = "money_accounts"
    __table_args__ = (
        Index("ix_money_accounts_payment_method_id", "payment_method_id"),
        Index("ix_money_accounts_type", "type"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[MoneyAccountType] = mapped_column(
        Enum(MoneyAccountType, native_enum=False, length=20), nullable=False
    )
    payment_method_id: Mapped[int] = mapped_column(
        ID_TYPE,
        ForeignKey("payment_methods.id", ondelete="RESTRICT"),
        nullable=True,
    )
    account_no: Mapped[str] = mapped_column(String(50), nullable=True)
    opening_balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00"), server_default=text("0.00")
    )
    allow_overdraft: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0")
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