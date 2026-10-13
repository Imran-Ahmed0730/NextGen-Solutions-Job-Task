from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.money_accounts import service
from app.modules.money_accounts.models import MoneyAccount
from app.modules.money_accounts.schemas import (
    MoneyAccountCreate,
    MoneyAccountResponse,
    MoneyAccountUpdate,
)

router = APIRouter(prefix="/api/v1/money-accounts", tags=["money-accounts"])


def _account_or_404(db: Session, account_id: int) -> MoneyAccount:
    account = service.get_money_account(db, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Money account not found")
    return account


@router.get("", response_model=list[MoneyAccountResponse])
def list_money_accounts(
    include_inactive: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master_data.money_accounts.read")),
) -> list[MoneyAccount]:
    return service.list_money_accounts(
        db, include_inactive=include_inactive, offset=offset, limit=limit
    )


@router.post("", response_model=MoneyAccountResponse, status_code=status.HTTP_201_CREATED)
def create_money_account(
    payload: MoneyAccountCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.money_accounts.create")),
) -> MoneyAccount:
    return service.create_money_account(db, payload.model_dump(), actor, _ip(request))


@router.get("/{account_id}", response_model=MoneyAccountResponse)
def get_money_account(
    account_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master_data.money_accounts.read")),
) -> MoneyAccount:
    return _account_or_404(db, account_id)


@router.patch("/{account_id}", response_model=MoneyAccountResponse)
def update_money_account(
    account_id: int,
    payload: MoneyAccountUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.money_accounts.update")),
) -> MoneyAccount:
    account = _account_or_404(db, account_id)
    return service.update_money_account(
        db, account, payload.model_dump(exclude_unset=True), actor, _ip(request)
    )


@router.delete("/{account_id}", response_model=MoneyAccountResponse)
def delete_money_account(
    account_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.money_accounts.delete")),
) -> MoneyAccount:
    return service.delete_money_account(
        db, _account_or_404(db, account_id), actor, _ip(request)
    )


@router.post("/{account_id}/activate", response_model=MoneyAccountResponse)
def activate_money_account(
    account_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.money_accounts.update")),
) -> MoneyAccount:
    return service.activate_money_account(
        db, _account_or_404(db, account_id), actor, _ip(request)
    )


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None