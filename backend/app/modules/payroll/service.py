import calendar
from datetime import UTC, date, datetime, time
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.document_numbering.service import generate_next_number
from app.modules.money_accounts.models import MoneyAccount
from app.modules.money_transactions.models import MoneyTransactionType
from app.modules.money_transactions.service import post_money_transaction
from app.modules.payroll import repository
from app.modules.payroll.models import PayrollLine, PayrollRun
from app.modules.payroll.schemas import (
    PayrollAccountOption,
    PayrollOptionsResponse,
    PayrollRunCreate,
)

DOCUMENT_TYPE = "PAYROLL"


def list_runs(db: Session, *, offset: int = 0, limit: int = 50) -> list[PayrollRun]:
    return repository.list_runs(db, offset=offset, limit=limit)


def get_run(db: Session, run_id: int) -> PayrollRun:
    run = repository.get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    return run


def get_options(db: Session) -> PayrollOptionsResponse:
    return PayrollOptionsResponse(
        accounts=[
            PayrollAccountOption(id=account.id, name=account.name, type=account.type.value)
            for account in repository.list_active_accounts(db)
        ]
    )


def create_run(
    db: Session, payload: PayrollRunCreate, actor: User, ip: str | None = None
) -> PayrollRun:
    period_end = date(
        payload.period_year,
        payload.period_month,
        calendar.monthrange(payload.period_year, payload.period_month)[1],
    )
    employees = repository.list_period_employees(db, period_end)
    if not employees:
        raise HTTPException(
            status_code=422, detail="No active employees are eligible for this payroll period"
        )

    lines = [
        PayrollLine(
            employee_id=employee.id,
            base_salary=employee.base_salary,
            deductions=Decimal("0.00"),
            net_pay=employee.base_salary,
        )
        for employee in employees
    ]
    run = PayrollRun(
        period_month=payload.period_month,
        period_year=payload.period_year,
        status="DRAFT",
        total_amount=sum((line.net_pay for line in lines), Decimal("0.00")),
        created_by=actor.id,
        lines=lines,
    )
    db.add(run)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Payroll already exists for this period"
        ) from exc

    record_audit(
        db,
        actor_id=actor.id,
        entity_type="payroll_run",
        entity_id=run.id,
        action="CREATE",
        after=_snapshot(run),
        ip=ip,
    )
    db.commit()
    result = repository.get_run(db, run.id)
    if result is None:
        raise RuntimeError("Created payroll run could not be reloaded")
    return result


def update_line(
    db: Session,
    run_id: int,
    line_id: int,
    deductions: Decimal,
    actor: User,
    ip: str | None = None,
) -> PayrollRun:
    try:
        run = repository.get_run(db, run_id, for_update=True)
        if run is None:
            raise HTTPException(status_code=404, detail="Payroll run not found")
        if run.status != "DRAFT":
            raise HTTPException(status_code=409, detail="Posted payroll is immutable")
        line = repository.get_line(db, line_id, for_update=True)
        if line is None or line.run_id != run.id:
            raise HTTPException(status_code=404, detail="Payroll line not found")
        if deductions > line.base_salary:
            raise HTTPException(
                status_code=422, detail="Deductions cannot exceed the employee's base salary"
            )
        before_total = run.total_amount
        before = _line_snapshot(line)
        line.deductions = deductions
        line.net_pay = line.base_salary - deductions
        run.total_amount = sum((item.net_pay for item in run.lines), Decimal("0.00"))
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="payroll_line",
            entity_id=line.id,
            action="UPDATE",
            before=before,
            after=_line_snapshot(line),
            ip=ip,
        )
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="payroll_run",
            entity_id=run.id,
            action="UPDATE",
            before={"total_amount": str(before_total)},
            after={"total_amount": str(run.total_amount)},
            ip=ip,
        )
        db.commit()
        result = repository.get_run(db, run.id)
        if result is None:
            raise RuntimeError("Updated payroll run could not be reloaded")
        return result
    except Exception:
        db.rollback()
        raise


def post_run(
    db: Session,
    run_id: int,
    *,
    account_id: int,
    paid_on: date,
    actor: User,
    ip: str | None = None,
) -> PayrollRun:
    try:
        run = repository.get_run(db, run_id, for_update=True)
        if run is None:
            raise HTTPException(status_code=404, detail="Payroll run not found")
        if run.status != "DRAFT":
            raise HTTPException(status_code=409, detail="Payroll run is already posted")
        if not run.lines:
            raise HTTPException(status_code=422, detail="Payroll run has no employee lines")
        if run.total_amount <= 0:
            raise HTTPException(status_code=422, detail="Payroll total must be greater than zero")
        account = db.get(MoneyAccount, account_id)
        if account is None or not account.is_active or account.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Active money account not found")

        before = _snapshot(run)
        run.doc_no = generate_next_number(db, DOCUMENT_TYPE, run.period_year)
        run.account_id = account.id
        run.paid_on = paid_on
        for line in run.lines:
            if line.net_pay == 0:
                continue
            transaction = post_money_transaction(
                db,
                account_id=account.id,
                amount_signed=-line.net_pay,
                txn_type=MoneyTransactionType.SALARY,
                actor=actor,
                txn_date=datetime.combine(paid_on, time.min, tzinfo=UTC),
                source_type=DOCUMENT_TYPE,
                source_id=run.id,
                party_type="EMPLOYEE",
                party_id=line.employee_id,
                note=f"Payroll {run.doc_no} - {line.employee.name}",
                ip=ip,
            )
            line.paid_txn_id = transaction.id
        run.status = "POSTED"
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="payroll_run",
            entity_id=run.id,
            action="POST",
            before=before,
            after=_snapshot(run),
            ip=ip,
        )
        db.commit()
        result = repository.get_run(db, run.id)
        if result is None:
            raise RuntimeError("Posted payroll run could not be reloaded")
        return result
    except Exception:
        db.rollback()
        raise


def _line_snapshot(line: PayrollLine) -> dict[str, object]:
    return {
        "employee_id": line.employee_id,
        "base_salary": str(line.base_salary),
        "deductions": str(line.deductions),
        "net_pay": str(line.net_pay),
    }


def _snapshot(run: PayrollRun) -> dict[str, object]:
    return {
        "doc_no": run.doc_no,
        "period_month": run.period_month,
        "period_year": run.period_year,
        "status": run.status,
        "total_amount": str(run.total_amount),
        "paid_on": run.paid_on.isoformat() if run.paid_on else None,
        "account_id": run.account_id,
        "lines": [_line_snapshot(line) for line in run.lines],
    }
