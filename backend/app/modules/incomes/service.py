from datetime import UTC, datetime, time

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.document_numbering.service import generate_next_number
from app.modules.income_categories import service as income_category_service
from app.modules.incomes import repository
from app.modules.incomes.models import Income
from app.modules.incomes.schemas import (
    IncomeAccountOption,
    IncomeCategoryOption,
    IncomeCreate,
    IncomeOptionsResponse,
)
from app.modules.money_accounts import service as money_account_service
from app.modules.money_transactions.models import MoneyTransactionType
from app.modules.money_transactions.service import post_money_transaction

DOCUMENT_TYPE = "INCOME"


def list_incomes(db: Session, *, offset: int = 0, limit: int = 50) -> list[Income]:
    return repository.list_incomes(db, offset=offset, limit=limit)


def get_income(db: Session, income_id: int) -> Income | None:
    return repository.get_income(db, income_id)


def get_income_options(db: Session) -> IncomeOptionsResponse:
    categories = income_category_service.list_categories(db, limit=200)
    accounts = money_account_service.list_money_accounts(db, limit=200)
    return IncomeOptionsResponse(
        categories=[
            IncomeCategoryOption(id=item.id, name=item.name)
            for item in categories
        ],
        accounts=[
            IncomeAccountOption(id=item.id, name=item.name, type=item.type.value)
            for item in accounts
        ],
    )


def create_income(
    db: Session,
    payload: IncomeCreate,
    actor: User,
    ip: str | None = None,
) -> Income:
    try:
        category = repository.get_category_for_update(db, payload.category_id)
        if category is None or not category.is_active or category.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Income category not found")
        account = repository.get_account_for_update(db, payload.account_id)
        if account is None or not account.is_active or account.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Active money account not found")

        income = Income(
            doc_no=generate_next_number(db, DOCUMENT_TYPE, payload.doc_date.year),
            doc_date=payload.doc_date,
            category_id=category.id,
            account_id=account.id,
            amount=payload.amount,
            status="POSTED",
            note=payload.note,
            created_by=actor.id,
        )
        db.add(income)
        db.flush()

        post_money_transaction(
            db,
            account_id=account.id,
            amount_signed=payload.amount,
            txn_type=MoneyTransactionType.INCOME,
            actor=actor,
            txn_date=datetime.combine(payload.doc_date, time.min, tzinfo=UTC),
            source_type=DOCUMENT_TYPE,
            source_id=income.id,
            party_type=None,
            party_id=None,
            note=payload.note or f"Income: {category.name}",
            ip=ip,
        )

        record_audit(
            db,
            actor_id=actor.id,
            entity_type="income",
            entity_id=income.id,
            action="CREATE",
            after=_snapshot(income),
            ip=ip,
        )
        db.commit()
        db.refresh(income)
        return income
    except Exception:
        db.rollback()
        raise


def _snapshot(income: Income) -> dict[str, object]:
    return {
        "doc_no": income.doc_no,
        "doc_date": income.doc_date.isoformat(),
        "category_id": income.category_id,
        "account_id": income.account_id,
        "amount": str(income.amount),
        "status": income.status,
        "note": income.note,
    }
