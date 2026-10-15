from datetime import datetime

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.money_transactions import service
from app.modules.money_transactions.schemas import (
    AccountLedgerResponse,
    MoneyAccountBalanceItem,
    MoneyAccountBalanceResponse,
)

router = APIRouter(prefix="/api/v1/money-transactions", tags=["money-transactions"])


@router.get(
    "/accounts",
    response_model=list[MoneyAccountBalanceItem],
)
def list_money_account_balances(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("money.transactions.read")),
) -> list[MoneyAccountBalanceItem]:
    return service.list_account_balances(db)


@router.get(
    "/accounts/{account_id}/balance",
    response_model=MoneyAccountBalanceResponse,
)
def get_money_account_balance(
    account_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("money.transactions.read")),
) -> MoneyAccountBalanceResponse:
    return MoneyAccountBalanceResponse(
        account_id=account_id,
        balance=service.get_account_balance(db, account_id),
    )


@router.get(
    "/accounts/{account_id}/ledger",
    response_model=AccountLedgerResponse,
)
def get_money_account_ledger(
    account_id: int = Path(ge=1),
    from_date: datetime | None = Query(default=None),
    to_date: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("money.transactions.read")),
) -> AccountLedgerResponse:
    return service.get_account_ledger(db, account_id, from_date=from_date, to_date=to_date)
