from datetime import UTC, datetime, time

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.document_numbering.service import generate_next_number
from app.modules.expense_categories import service as expense_category_service
from app.modules.expenses import repository
from app.modules.expenses.models import Expense
from app.modules.expenses.schemas import (
    ExpenseAccountOption,
    ExpenseCategoryOption,
    ExpenseCreate,
    ExpenseOptionsResponse,
)
from app.modules.money_accounts import service as money_account_service
from app.modules.money_transactions.models import MoneyTransactionType
from app.modules.money_transactions.service import post_money_transaction

DOCUMENT_TYPE = "EXPENSE"


def list_expenses(db: Session, *, offset: int = 0, limit: int = 50) -> list[Expense]:
    return repository.list_expenses(db, offset=offset, limit=limit)


def get_expense(db: Session, expense_id: int) -> Expense | None:
    return repository.get_expense(db, expense_id)


def get_expense_options(db: Session) -> ExpenseOptionsResponse:
    categories = expense_category_service.list_categories(db, limit=200)
    accounts = money_account_service.list_money_accounts(db, limit=200)
    return ExpenseOptionsResponse(
        categories=[
            ExpenseCategoryOption(id=item.id, name=item.name)
            for item in categories
        ],
        accounts=[
            ExpenseAccountOption(id=item.id, name=item.name, type=item.type.value)
            for item in accounts
        ],
    )


def create_expense(
    db: Session,
    payload: ExpenseCreate,
    actor: User,
    ip: str | None = None,
) -> Expense:
    try:
        category = repository.get_category_for_update(db, payload.category_id)
        if category is None or not category.is_active or category.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Expense category not found")
        account = repository.get_account_for_update(db, payload.account_id)
        if account is None or not account.is_active or account.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Active money account not found")

        expense = Expense(
            doc_no=generate_next_number(db, DOCUMENT_TYPE, payload.doc_date.year),
            doc_date=payload.doc_date,
            category_id=category.id,
            account_id=account.id,
            amount=payload.amount,
            paid_to=payload.paid_to,
            status="POSTED",
            note=payload.note,
            created_by=actor.id,
        )
        db.add(expense)
        db.flush()

        post_money_transaction(
            db,
            account_id=account.id,
            amount_signed=-payload.amount,
            txn_type=MoneyTransactionType.EXPENSE,
            actor=actor,
            txn_date=datetime.combine(payload.doc_date, time.min, tzinfo=UTC),
            source_type=DOCUMENT_TYPE,
            source_id=expense.id,
            party_type=None,
            party_id=None,
            note=payload.note or f"Expense: {category.name}",
            ip=ip,
        )

        record_audit(
            db,
            actor_id=actor.id,
            entity_type="expense",
            entity_id=expense.id,
            action="CREATE",
            after=_snapshot(expense),
            ip=ip,
        )
        db.commit()
        db.refresh(expense)
        return expense
    except Exception:
        db.rollback()
        raise


def _snapshot(expense: Expense) -> dict[str, object]:
    return {
        "doc_no": expense.doc_no,
        "doc_date": expense.doc_date.isoformat(),
        "category_id": expense.category_id,
        "account_id": expense.account_id,
        "amount": str(expense.amount),
        "paid_to": expense.paid_to,
        "status": expense.status,
        "note": expense.note,
    }
