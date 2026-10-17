import enum
from datetime import datetime
from decimal import Decimal

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
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

ID_TYPE = (
    BigInteger().with_variant(BIGINT(unsigned=True), "mysql").with_variant(Integer(), "sqlite")
)


class MoneyTransactionType(str, enum.Enum):
    COLLECTION = "COLLECTION"
    PAYMENT = "PAYMENT"
    EXPENSE = "EXPENSE"
    INCOME = "INCOME"
    TRANSFER_OUT = "TRANSFER_OUT"
    TRANSFER_IN = "TRANSFER_IN"
    OPENING = "OPENING"
    PURCHASE_PAYMENT = "PURCHASE_PAYMENT"
    SALARY = "SALARY"


class MoneyTransaction(Base):
    __tablename__ = "money_transactions"
    __table_args__ = (
        CheckConstraint("amount_signed <> 0", name="ck_money_transactions_nonzero_amount"),
        CheckConstraint(
            "txn_type IN ('COLLECTION', 'PAYMENT', 'EXPENSE', 'INCOME', "
            "'TRANSFER_OUT', 'TRANSFER_IN', 'OPENING', 'PURCHASE_PAYMENT', 'SALARY')",
            name="ck_money_transactions_txn_type",
        ),
        Index("ix_money_transactions_account_date", "account_id", "txn_date"),
        Index("ix_money_transactions_txn_date", "txn_date"),
        Index("ix_money_transactions_source", "source_type", "source_id"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    txn_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    account_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("money_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    amount_signed: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    txn_type: Mapped[MoneyTransactionType] = mapped_column(
        Enum(
            MoneyTransactionType,
            native_enum=False,
            length=30,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=True)
    source_id: Mapped[int] = mapped_column(ID_TYPE, nullable=True)
    party_type: Mapped[str] = mapped_column(String(20), nullable=True)
    party_id: Mapped[int] = mapped_column(ID_TYPE, nullable=True)
    note: Mapped[str] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
