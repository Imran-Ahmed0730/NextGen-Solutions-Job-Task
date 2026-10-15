from datetime import UTC, datetime, time

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.customers import service as customer_service
from app.modules.document_numbering.service import generate_next_number
from app.modules.money_accounts import service as money_account_service
from app.modules.money_accounts.models import MoneyAccount
from app.modules.money_collections import repository
from app.modules.money_collections.models import CustomerCollection
from app.modules.money_collections.schemas import (
    CollectionAccountOption,
    CollectionCustomerOption,
    CustomerCollectionCreate,
    CustomerCollectionOptionsResponse,
)
from app.modules.money_transactions.models import MoneyTransactionType
from app.modules.money_transactions.service import post_money_transaction

DOCUMENT_TYPE = "CUSTOMER_COLLECTION"


def list_collections(db: Session, *, offset: int = 0, limit: int = 50) -> list[CustomerCollection]:
    return repository.list_collections(db, offset=offset, limit=limit)


def get_collection_options(db: Session) -> CustomerCollectionOptionsResponse:
    customers = customer_service.list_customers(db, limit=200)
    accounts = money_account_service.list_money_accounts(db, limit=200)
    return CustomerCollectionOptionsResponse(
        customers=[
            CollectionCustomerOption(id=item.id, code=item.code, name=item.name)
            for item in customers
        ],
        accounts=[
            CollectionAccountOption(id=item.id, name=item.name, type=item.type.value)
            for item in accounts
        ],
    )


def create_collection(
    db: Session,
    payload: CustomerCollectionCreate,
    actor: User,
    ip: str | None = None,
) -> CustomerCollection:
    try:
        customer = repository.get_customer_for_update(db, payload.customer_id)
        if customer is None or not customer.is_active or customer.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Customer not found")
        account = db.get(MoneyAccount, payload.account_id)
        if account is None or not account.is_active or account.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Active money account not found")

        collection = CustomerCollection(
            doc_no=generate_next_number(db, DOCUMENT_TYPE, payload.doc_date.year),
            doc_date=payload.doc_date,
            customer_id=customer.id,
            account_id=payload.account_id,
            amount=payload.amount,
            method_ref=payload.method_ref,
            status="POSTED",
            note=payload.note,
            created_by=actor.id,
        )
        db.add(collection)
        db.flush()
        post_money_transaction(
            db,
            account_id=account.id,
            amount_signed=payload.amount,
            txn_type=MoneyTransactionType.COLLECTION,
            actor=actor,
            txn_date=datetime.combine(payload.doc_date, time.min, tzinfo=UTC),
            source_type=DOCUMENT_TYPE,
            source_id=collection.id,
            party_type="CUSTOMER",
            party_id=customer.id,
            note=payload.note,
            ip=ip,
        )
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="customer_collection",
            entity_id=collection.id,
            action="CREATE",
            after=_snapshot(collection),
            ip=ip,
        )
        db.commit()
        db.refresh(collection)
        return collection
    except Exception:
        db.rollback()
        raise


def _snapshot(collection: CustomerCollection) -> dict[str, object]:
    return {
        "doc_no": collection.doc_no,
        "doc_date": collection.doc_date.isoformat(),
        "customer_id": collection.customer_id,
        "account_id": collection.account_id,
        "amount": str(collection.amount),
        "method_ref": collection.method_ref,
        "status": collection.status,
        "note": collection.note,
    }


def due_entry_data(collection: CustomerCollection) -> dict[str, object]:
    return {
        "date": collection.doc_date.isoformat(),
        "type": "COLLECTION",
        "description": f"Customer Collection {collection.doc_no}",
        "amount": -collection.amount,
    }
