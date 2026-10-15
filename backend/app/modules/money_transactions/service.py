from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.money_transactions import repository
from app.modules.money_transactions.models import MoneyTransaction, MoneyTransactionType
from app.modules.money_transactions.schemas import AccountLedgerResponse, LedgerEntry

CENT = Decimal("0.01")
MAX_AMOUNT = Decimal("9999999999999999.99")
INFLOW_TYPES = frozenset(
    {
        MoneyTransactionType.COLLECTION,
        MoneyTransactionType.INCOME,
        MoneyTransactionType.TRANSFER_IN,
    }
)
OUTFLOW_TYPES = frozenset(
    {
        MoneyTransactionType.PAYMENT,
        MoneyTransactionType.EXPENSE,
        MoneyTransactionType.TRANSFER_OUT,
        MoneyTransactionType.PURCHASE_PAYMENT,
        MoneyTransactionType.SALARY,
    }
)


def get_account_balance(db: Session, account_id: int) -> Decimal:
    account = repository.get_account_for_balance(db, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Money account not found")
    return repository.get_account_balance(db, account)


def get_account_balance_for_update(db: Session, account_id: int) -> Decimal:
    account = repository.get_account_for_update(db, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Money account not found")
    return repository.get_account_balance_for_update(db, account)


def has_account_transactions(db: Session, account_id: int) -> bool:
    return repository.has_transactions(db, account_id)


def post_money_transaction(
    db: Session,
    *,
    account_id: int,
    amount_signed: Decimal,
    txn_type: MoneyTransactionType,
    actor: User,
    txn_date: datetime | None = None,
    source_type: str | None = None,
    source_id: int | None = None,
    party_type: str | None = None,
    party_id: int | None = None,
    note: str | None = None,
    ip: str | None = None,
) -> MoneyTransaction:
    if not isinstance(account_id, int) or isinstance(account_id, bool) or account_id <= 0:
        raise HTTPException(status_code=422, detail="Account ID must be a positive integer")
    _validate_amount(amount_signed)
    _validate_type_and_sign(txn_type, amount_signed)
    posted_at = txn_date or datetime.now(UTC)
    if posted_at.tzinfo is None or posted_at.utcoffset() is None:
        raise HTTPException(status_code=422, detail="Transaction date must include a timezone")
    _validate_optional_text(source_type, "Source type", 50)
    _validate_optional_text(party_type, "Party type", 20)
    if source_id is not None and (
        not isinstance(source_id, int) or isinstance(source_id, bool) or source_id <= 0
    ):
        raise HTTPException(status_code=422, detail="Source ID must be a positive integer")
    if party_id is not None and (
        not isinstance(party_id, int) or isinstance(party_id, bool) or party_id <= 0
    ):
        raise HTTPException(status_code=422, detail="Party ID must be a positive integer")
    if (party_type is None) != (party_id is None):
        raise HTTPException(status_code=422, detail="Party type and ID must be provided together")
    if note is not None and not isinstance(note, str):
        raise HTTPException(status_code=422, detail="Note must be text")

    account = repository.get_account_for_update(db, account_id)
    if account is None or not account.is_active or account.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Active money account not found")

    resulting_balance = repository.get_account_balance_for_update(db, account) + amount_signed
    if resulting_balance < 0 and not account.allow_overdraft:
        raise HTTPException(status_code=409, detail="MONEY_ACCOUNT_INSUFFICIENT")

    transaction = repository.create_transaction(
        db,
        txn_date=posted_at,
        account_id=account.id,
        amount_signed=amount_signed,
        txn_type=txn_type,
        source_type=source_type.strip() if source_type else None,
        source_id=source_id,
        party_type=party_type.strip() if party_type else None,
        party_id=party_id,
        note=note,
        created_by=actor.id,
    )
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="money_transaction",
        entity_id=transaction.id,
        action="CREATE",
        after=_snapshot(transaction),
        ip=ip,
    )
    db.flush()
    return transaction


def _validate_amount(value: Decimal) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value == 0:
        raise HTTPException(
            status_code=422, detail="Transaction amount must be a finite non-zero decimal"
        )
    if abs(value) > MAX_AMOUNT:
        raise HTTPException(status_code=422, detail="Transaction amount exceeds supported amount")
    try:
        if value.quantize(CENT) != value:
            raise HTTPException(
                status_code=422,
                detail="Transaction amount cannot have more than two decimal places",
            )
    except InvalidOperation as exc:
        raise HTTPException(status_code=422, detail="Transaction amount is invalid") from exc


def _validate_type_and_sign(txn_type: MoneyTransactionType, amount_signed: Decimal) -> None:
    if not isinstance(txn_type, MoneyTransactionType):
        raise HTTPException(status_code=422, detail="Invalid money transaction type")
    if txn_type in INFLOW_TYPES and amount_signed < 0:
        raise HTTPException(status_code=422, detail="Transaction type requires a positive amount")
    if txn_type in OUTFLOW_TYPES and amount_signed > 0:
        raise HTTPException(status_code=422, detail="Transaction type requires a negative amount")


def _validate_optional_text(value: str | None, label: str, max_length: int) -> None:
    if value is not None and (
        not isinstance(value, str) or not value.strip() or len(value.strip()) > max_length
    ):
        raise HTTPException(
            status_code=422, detail=f"{label} must contain 1 to {max_length} characters"
        )


def _snapshot(transaction: MoneyTransaction) -> dict[str, object]:
    return {
        "txn_date": transaction.txn_date.isoformat(),
        "account_id": transaction.account_id,
        "amount_signed": str(transaction.amount_signed),
        "txn_type": transaction.txn_type.value,
        "source_type": transaction.source_type,
        "source_id": transaction.source_id,
        "party_type": transaction.party_type,
        "party_id": transaction.party_id,
        "note": transaction.note,
    }


def get_account_ledger(
    db: Session,
    account_id: int,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> AccountLedgerResponse:
    account = repository.get_account_for_balance(db, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Money account not found")

    opening_balance, transactions = repository.list_account_transactions(
        db, account, from_date=from_date, to_date=to_date
    )

    running = opening_balance
    entries: list[LedgerEntry] = []
    total_inflow = Decimal("0.00")
    total_outflow = Decimal("0.00")

    for txn in transactions:
        running += txn.amount_signed
        if txn.amount_signed > 0:
            total_inflow += txn.amount_signed
        else:
            total_outflow += abs(txn.amount_signed)

        entries.append(
            LedgerEntry(
                id=txn.id,
                txn_date=txn.txn_date,
                amount_signed=txn.amount_signed,
                txn_type=txn.txn_type.value,
                source_type=txn.source_type,
                source_id=txn.source_id,
                party_type=txn.party_type,
                party_id=txn.party_id,
                note=txn.note,
                running_balance=running,
            )
        )

    return AccountLedgerResponse(
        account_id=account.id,
        account_name=account.name,
        opening_balance=opening_balance,
        closing_balance=running,
        total_inflow=total_inflow,
        total_outflow=total_outflow,
        entries=entries,
    )

