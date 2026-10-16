from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
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


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (
        UniqueConstraint("code", name="uq_employees_code"),
        CheckConstraint("base_salary >= 0", name="ck_employees_base_salary_nonnegative"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    mobile: Mapped[str] = mapped_column(String(30), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=True)
    designation: Mapped[str] = mapped_column(String(100), nullable=True)
    department: Mapped[str] = mapped_column(String(100), nullable=True)
    join_date: Mapped[date] = mapped_column(Date, nullable=False)
    base_salary: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("1"))
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
