from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.modules.employees.models import Employee
from app.modules.money_accounts.models import MoneyAccount
from app.modules.payroll.models import PayrollLine, PayrollRun


def list_runs(db: Session, *, offset: int, limit: int) -> list[PayrollRun]:
    statement = (
        select(PayrollRun)
        .options(selectinload(PayrollRun.lines).joinedload(PayrollLine.employee))
        .order_by(PayrollRun.period_year.desc(), PayrollRun.period_month.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(statement))


def get_run(db: Session, run_id: int, *, for_update: bool = False) -> PayrollRun | None:
    statement = (
        select(PayrollRun)
        .options(selectinload(PayrollRun.lines).joinedload(PayrollLine.employee))
        .where(PayrollRun.id == run_id)
    )
    if for_update:
        statement = statement.with_for_update()
    return db.scalar(statement)


def get_line(db: Session, line_id: int, *, for_update: bool = False) -> PayrollLine | None:
    statement = (
        select(PayrollLine)
        .options(joinedload(PayrollLine.employee))
        .where(PayrollLine.id == line_id)
    )
    if for_update:
        statement = statement.with_for_update()
    return db.scalar(statement)


def list_period_employees(db: Session, period_end: date) -> list[Employee]:
    statement = (
        select(Employee)
        .where(
            Employee.is_active.is_(True),
            Employee.deleted_at.is_(None),
            Employee.join_date <= period_end,
        )
        .order_by(Employee.name, Employee.id)
    )
    return list(db.scalars(statement))


def list_active_accounts(db: Session) -> list[MoneyAccount]:
    statement = (
        select(MoneyAccount)
        .where(MoneyAccount.is_active.is_(True), MoneyAccount.deleted_at.is_(None))
        .order_by(MoneyAccount.name, MoneyAccount.id)
    )
    return list(db.scalars(statement))
