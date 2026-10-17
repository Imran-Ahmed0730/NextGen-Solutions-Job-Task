from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.modules.employees.models import Employee

ID_TYPE = (
    BigInteger().with_variant(BIGINT(unsigned=True), "mysql").with_variant(Integer(), "sqlite")
)


class PayrollRun(Base):
    __tablename__ = "payroll_runs"
    __table_args__ = (
        UniqueConstraint("doc_no", name="uq_payroll_runs_doc_no"),
        UniqueConstraint("period_month", "period_year", name="uq_payroll_runs_period"),
        CheckConstraint("period_month BETWEEN 1 AND 12", name="ck_payroll_runs_month"),
        CheckConstraint("status IN ('DRAFT', 'POSTED')", name="ck_payroll_runs_status"),
        CheckConstraint("total_amount >= 0", name="ck_payroll_runs_total_nonnegative"),
        Index("ix_payroll_runs_paid_on", "paid_on"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    doc_no: Mapped[str] = mapped_column(String(50), nullable=True)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="DRAFT")
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, server_default=text("0.00")
    )
    paid_on: Mapped[date] = mapped_column(Date, nullable=True)
    account_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("money_accounts.id", ondelete="RESTRICT"), nullable=True
    )
    created_by: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    lines: Mapped[list["PayrollLine"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="PayrollLine.id",
    )


class PayrollLine(Base):
    __tablename__ = "payroll_lines"
    __table_args__ = (
        UniqueConstraint("run_id", "employee_id", name="uq_payroll_lines_run_employee"),
        CheckConstraint("base_salary >= 0", name="ck_payroll_lines_salary_nonnegative"),
        CheckConstraint("deductions >= 0", name="ck_payroll_lines_deductions_nonnegative"),
        CheckConstraint(
            "deductions <= base_salary", name="ck_payroll_lines_deductions_within_salary"
        ),
        CheckConstraint("net_pay >= 0", name="ck_payroll_lines_net_nonnegative"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    base_salary: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    deductions: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, server_default=text("0.00")
    )
    net_pay: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    paid_txn_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("money_transactions.id", ondelete="RESTRICT"), nullable=True
    )
    run: Mapped[PayrollRun] = relationship(back_populates="lines")
    employee: Mapped[Employee] = relationship(lazy="joined")
