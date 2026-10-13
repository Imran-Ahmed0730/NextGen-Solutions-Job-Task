from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.money_accounts import repository
from app.modules.money_accounts.models import MoneyAccount, MoneyAccountType
from app.modules.payment_methods.models import PaymentMethod


def list_money_accounts(
    db: Session, *, include_inactive: bool = False, offset: int = 0, limit: int = 50
) -> list[MoneyAccount]:
    return repository.list_money_accounts(
        db, include_inactive=include_inactive, offset=offset, limit=limit
    )


def get_money_account(db: Session, account_id: int) -> MoneyAccount | None:
    return repository.get_money_account(db, account_id)


def create_money_account(
    db: Session, data: dict[str, object], actor: User, ip: str | None = None
) -> MoneyAccount:
    name = _validate_name(data.get("name"))
    account_type = _validate_type(data.get("type"))
    payment_method_id = _validate_payment_method(db, data.get("payment_method_id"))
    account_no = _validate_account_no(data.get("account_no"))
    opening_balance = _validate_balance(data.get("opening_balance"), default=Decimal("0.00"))
    if not isinstance(data.get("allow_overdraft", False), bool):
        raise HTTPException(status_code=422, detail="allow_overdraft must be a boolean")
    if not isinstance(data.get("is_active", True), bool):
        raise HTTPException(status_code=422, detail="is_active must be a boolean")

    account = MoneyAccount(
        name=name,
        type=account_type,
        payment_method_id=payment_method_id,
        account_no=account_no,
        opening_balance=opening_balance,
        allow_overdraft=bool(data.get("allow_overdraft", False)),
        is_active=bool(data.get("is_active", True)),
    )
    db.add(account)
    db.flush()
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="money_account",
        entity_id=account.id,
        action="CREATE",
        after=_snapshot(account),
        ip=ip,
    )
    db.commit()
    db.refresh(account)
    return account


def update_money_account(
    db: Session,
    account: MoneyAccount,
    data: dict[str, object],
    actor: User,
    ip: str | None = None,
) -> MoneyAccount:
    if account.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Money account not found")

    name = account.name
    if "name" in data:
        name = _validate_name(data["name"])

    account_type = account.type
    if "type" in data:
        account_type = _validate_type(data["type"])

    payment_method_id = account.payment_method_id
    if "payment_method_id" in data:
        payment_method_id = _validate_payment_method(db, data["payment_method_id"])

    account_no = account.account_no
    if "account_no" in data:
        account_no = _validate_account_no(data["account_no"])

    opening_balance = account.opening_balance
    if "opening_balance" in data:
        opening_balance = _validate_balance(
            data["opening_balance"], default=account.opening_balance
        )

    allow_overdraft = account.allow_overdraft
    if "allow_overdraft" in data:
        value = data["allow_overdraft"]
        if not isinstance(value, bool):
            raise HTTPException(status_code=422, detail="allow_overdraft must be a boolean")
        allow_overdraft = value

    is_active = account.is_active
    if "is_active" in data:
        value = data["is_active"]
        if not isinstance(value, bool):
            raise HTTPException(status_code=422, detail="is_active must be a boolean")
        is_active = value

    before = _snapshot(account)
    account.name = name
    account.type = account_type
    account.payment_method_id = payment_method_id
    account.account_no = account_no
    account.opening_balance = opening_balance
    account.allow_overdraft = allow_overdraft
    account.is_active = is_active
    db.flush()
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="money_account",
        entity_id=account.id,
        action=(
            "STATUS"
            if is_active != before["is_active"]
            and name == before["name"]
            and account_type == before["type"]
            and payment_method_id == before["payment_method_id"]
            and account_no == before["account_no"]
            and opening_balance == before["opening_balance"]
            and allow_overdraft == before["allow_overdraft"]
            else "UPDATE"
        ),
        before=before,
        after=_snapshot(account),
        ip=ip,
    )
    db.commit()
    db.refresh(account)
    return account


def delete_money_account(
    db: Session, account: MoneyAccount, actor: User, ip: str | None = None
) -> MoneyAccount:
    if account.deleted_at is not None:
        return account
    before = _snapshot(account)
    account.is_active = False
    account.deleted_at = datetime.now(UTC)
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="money_account",
        entity_id=account.id,
        action="DELETE",
        before=before,
        after=_snapshot(account),
        ip=ip,
    )
    db.commit()
    db.refresh(account)
    return account


def activate_money_account(
    db: Session, account: MoneyAccount, actor: User, ip: str | None = None
) -> MoneyAccount:
    if account.is_active and account.deleted_at is None:
        return account
    before = _snapshot(account)
    account.is_active = True
    setattr(account, "deleted_at", None)
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="money_account",
        entity_id=account.id,
        action="STATUS",
        before=before,
        after=_snapshot(account),
        ip=ip,
    )
    db.commit()
    db.refresh(account)
    return account


def _validate_name(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=422, detail="Money account name is required")
    name = value.strip()
    if len(name) > 100:
        raise HTTPException(status_code=422, detail="Money account name is too long")
    return name


def _validate_type(value: object) -> MoneyAccountType:
    try:
        return value if isinstance(value, MoneyAccountType) else MoneyAccountType(str(value))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="Money account type is not valid") from exc


def _validate_payment_method(db: Session, value: object) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int):
        raise HTTPException(status_code=422, detail="Payment method id must be an integer")
    payment_method = db.get(PaymentMethod, value)
    if payment_method is None or payment_method.deleted_at is not None:
        raise HTTPException(status_code=400, detail="Payment method does not exist")
    return value


def _validate_account_no(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise HTTPException(status_code=422, detail="Account number must be text")
    account_no = value.strip()
    if not account_no:
        return None
    if len(account_no) > 50:
        raise HTTPException(status_code=422, detail="Account number is too long")
    return account_no


def _validate_balance(value: object, *, default: Decimal) -> Decimal:
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422, detail="Opening balance is not a valid number"
        ) from exc


def _snapshot(account: MoneyAccount) -> dict[str, object]:
    return {
        "name": account.name,
        "type": account.type.value if hasattr(account.type, "value") else str(account.type),
        "payment_method_id": account.payment_method_id,
        "account_no": account.account_no,
        "opening_balance": str(account.opening_balance),
        "allow_overdraft": account.allow_overdraft,
        "is_active": account.is_active,
        "deleted_at": account.deleted_at.isoformat() if account.deleted_at else None,
    }