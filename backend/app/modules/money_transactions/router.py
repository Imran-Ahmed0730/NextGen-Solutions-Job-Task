from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.money_transactions import service
from app.modules.money_transactions.schemas import MoneyAccountBalanceResponse

router = APIRouter(prefix="/api/v1/money-transactions", tags=["money-transactions"])


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
