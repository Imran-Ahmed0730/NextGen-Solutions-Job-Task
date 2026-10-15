from datetime import UTC, datetime, time

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.document_numbering.service import generate_next_number
from app.modules.fund_transfers import repository
from app.modules.fund_transfers.models import FundTransfer
from app.modules.fund_transfers.schemas import (
    FundTransferCreate,
    FundTransferOptionsResponse,
    TransferAccountOption,
)
from app.modules.money_accounts import service as money_account_service
from app.modules.money_transactions.models import MoneyTransactionType
from app.modules.money_transactions.service import post_money_transaction

DOCUMENT_TYPE = "FUND_TRANSFER"


def list_transfers(db: Session, *, offset: int = 0, limit: int = 50) -> list[FundTransfer]:
    return repository.list_transfers(db, offset=offset, limit=limit)


def get_transfer(db: Session, transfer_id: int) -> FundTransfer | None:
    return repository.get_transfer(db, transfer_id)


def get_transfer_options(db: Session) -> FundTransferOptionsResponse:
    accounts = money_account_service.list_money_accounts(db, limit=200)
    return FundTransferOptionsResponse(
        accounts=[
            TransferAccountOption(id=item.id, name=item.name, type=item.type.value)
            for item in accounts
        ],
    )


def create_transfer(
    db: Session,
    payload: FundTransferCreate,
    actor: User,
    ip: str | None = None,
) -> FundTransfer:
    if payload.from_account_id == payload.to_account_id:
        raise HTTPException(
            status_code=422, detail="Source and destination accounts must be different"
        )

    try:
        from_account = repository.get_account_for_update(db, payload.from_account_id)
        if from_account is None or not from_account.is_active or from_account.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Source money account not found")

        to_account = repository.get_account_for_update(db, payload.to_account_id)
        if to_account is None or not to_account.is_active or to_account.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Destination money account not found")

        transfer = FundTransfer(
            doc_no=generate_next_number(db, DOCUMENT_TYPE, payload.doc_date.year),
            doc_date=payload.doc_date,
            from_account_id=from_account.id,
            to_account_id=to_account.id,
            amount=payload.amount,
            status="POSTED",
            note=payload.note,
            created_by=actor.id,
        )
        db.add(transfer)
        db.flush()

        txn_time = datetime.combine(payload.doc_date, time.min, tzinfo=UTC)

        # 1. Post Outflow
        post_money_transaction(
            db,
            account_id=from_account.id,
            amount_signed=-payload.amount,
            txn_type=MoneyTransactionType.TRANSFER_OUT,
            actor=actor,
            txn_date=txn_time,
            source_type=DOCUMENT_TYPE,
            source_id=transfer.id,
            party_type=None,
            party_id=None,
            note=payload.note or f"Transfer to {to_account.name}",
            ip=ip,
        )

        # 2. Post Inflow
        post_money_transaction(
            db,
            account_id=to_account.id,
            amount_signed=payload.amount,
            txn_type=MoneyTransactionType.TRANSFER_IN,
            actor=actor,
            txn_date=txn_time,
            source_type=DOCUMENT_TYPE,
            source_id=transfer.id,
            party_type=None,
            party_id=None,
            note=payload.note or f"Transfer from {from_account.name}",
            ip=ip,
        )

        record_audit(
            db,
            actor_id=actor.id,
            entity_type="fund_transfer",
            entity_id=transfer.id,
            action="CREATE",
            after=_snapshot(transfer),
            ip=ip,
        )
        db.commit()
        db.refresh(transfer)
        return transfer
    except Exception:
        db.rollback()
        raise


def _snapshot(transfer: FundTransfer) -> dict[str, object]:
    return {
        "doc_no": transfer.doc_no,
        "doc_date": transfer.doc_date.isoformat(),
        "from_account_id": transfer.from_account_id,
        "to_account_id": transfer.to_account_id,
        "amount": str(transfer.amount),
        "status": transfer.status,
        "note": transfer.note,
    }

