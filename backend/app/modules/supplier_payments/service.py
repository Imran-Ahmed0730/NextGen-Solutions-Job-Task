from datetime import UTC, datetime, time
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.document_numbering.service import generate_next_number
from app.modules.money_accounts import service as money_account_service
from app.modules.money_accounts.models import MoneyAccount
from app.modules.money_transactions.models import MoneyTransactionType
from app.modules.money_transactions.service import post_money_transaction
from app.modules.supplier_payments import repository
from app.modules.supplier_payments.models import SupplierPayment, SupplierPaymentAllocation
from app.modules.supplier_payments.schemas import (
    SupplierPaymentAccountOption,
    SupplierPaymentAllocationCreate,
    SupplierPaymentBillOption,
    SupplierPaymentCreate,
    SupplierPaymentOptionsResponse,
    SupplierPaymentSupplierOption,
)
from app.modules.suppliers import service as supplier_service
from app.modules.suppliers.models import Supplier

DOCUMENT_TYPE = "SUPPLIER_PAYMENT"


def list_payments(db: Session, *, offset: int = 0, limit: int = 50) -> list[SupplierPayment]:
    return repository.list_payments(db, offset=offset, limit=limit)


def get_payment_options(db: Session) -> SupplierPaymentOptionsResponse:
    suppliers = supplier_service.list_suppliers(db, limit=200)
    accounts = money_account_service.list_money_accounts(db, limit=200)
    return SupplierPaymentOptionsResponse(
        suppliers=[
            SupplierPaymentSupplierOption(id=item.id, code=item.code, name=item.name)
            for item in suppliers
        ],
        accounts=[
            SupplierPaymentAccountOption(id=item.id, name=item.name, type=item.type.value)
            for item in accounts
        ],
    )


def list_bill_options(db: Session, supplier_id: int) -> list[SupplierPaymentBillOption]:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None or not supplier.is_active or supplier.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return _bill_options(db, supplier_id)


def create_payment(
    db: Session,
    payload: SupplierPaymentCreate,
    actor: User,
    ip: str | None = None,
) -> SupplierPayment:
    try:
        supplier = repository.get_supplier_for_update(db, payload.supplier_id)
        if supplier is None or not supplier.is_active or supplier.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Supplier not found")
        account = db.get(MoneyAccount, payload.account_id)
        if account is None or not account.is_active or account.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Active money account not found")
        if sum((item.amount for item in payload.allocations), Decimal("0.00")) > payload.amount:
            raise HTTPException(
                status_code=422, detail="Allocated amount cannot exceed payment amount"
            )
        if len({(item.ref_type, item.ref_id) for item in payload.allocations}) != len(
            payload.allocations
        ):
            raise HTTPException(status_code=422, detail="A bill can only be allocated once")

        _lock_and_validate_bills(db, supplier.id, payload.allocations)
        allocations = [
            SupplierPaymentAllocation(
                ref_type=item.ref_type,
                ref_id=item.ref_id,
                amount=item.amount,
            )
            for item in payload.allocations
        ]
        payment = SupplierPayment(
            doc_no=generate_next_number(db, DOCUMENT_TYPE, payload.doc_date.year),
            doc_date=payload.doc_date,
            supplier_id=supplier.id,
            account_id=payload.account_id,
            amount=payload.amount,
            status="POSTED",
            note=payload.note,
            created_by=actor.id,
            allocations=allocations,
        )
        db.add(payment)
        db.flush()
        post_money_transaction(
            db,
            account_id=payload.account_id,
            amount_signed=-payload.amount,
            txn_type=MoneyTransactionType.PURCHASE_PAYMENT,
            actor=actor,
            txn_date=datetime.combine(payload.doc_date, time.min, tzinfo=UTC),
            source_type=DOCUMENT_TYPE,
            source_id=payment.id,
            party_type="SUPPLIER",
            party_id=supplier.id,
            note=payload.note,
            ip=ip,
        )
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="supplier_payment",
            entity_id=payment.id,
            action="CREATE",
            after=_snapshot(payment),
            ip=ip,
        )
        db.commit()
        db.refresh(payment)
        return payment
    except Exception:
        db.rollback()
        raise


def _lock_and_validate_bills(
    db: Session,
    supplier_id: int,
    allocations: list[SupplierPaymentAllocationCreate],
) -> None:
    for allocation in sorted(allocations, key=lambda item: (item.ref_type, item.ref_id)):
        if allocation.ref_type == "RECEIPT":
            receipt = repository.get_receipt_for_update(db, allocation.ref_id)
            if receipt is None or receipt.supplier_id != supplier_id or receipt.status != "POSTED":
                raise HTTPException(status_code=404, detail="Goods receipt bill not found")
            bill_total = receipt.total - repository.get_returned_receipt_amount(db, receipt.id)
        else:
            purchase = repository.get_direct_purchase_for_update(db, allocation.ref_id)
            if (
                purchase is None
                or purchase.supplier_id != supplier_id
                or purchase.status != "POSTED"
            ):
                raise HTTPException(status_code=404, detail="Direct purchase bill not found")
            bill_total = purchase.total
        paid = repository.get_allocated_amount(
            db, ref_type=allocation.ref_type, ref_id=allocation.ref_id, for_update=True
        )
        remaining = bill_total - paid
        if allocation.amount > remaining:
            raise HTTPException(
                status_code=409,
                detail=f"SUPPLIER_BILL_ALLOCATION_EXCEEDS_OUTSTANDING:{allocation.ref_type}:{allocation.ref_id}",
            )


def _bill_options(db: Session, supplier_id: int) -> list[SupplierPaymentBillOption]:
    options: list[SupplierPaymentBillOption] = []
    for receipt in repository.list_receipt_bills(db, supplier_id):
        total = receipt.total - repository.get_returned_receipt_amount(db, receipt.id)
        paid = repository.get_allocated_amount(db, ref_type="RECEIPT", ref_id=receipt.id)
        if total > paid:
            options.append(
                SupplierPaymentBillOption(
                    ref_type="RECEIPT",
                    ref_id=receipt.id,
                    doc_no=receipt.doc_no,
                    doc_date=receipt.doc_date,
                    total=total,
                    paid=paid,
                    outstanding=total - paid,
                )
            )
    for purchase in repository.list_direct_purchase_bills(db, supplier_id):
        paid = repository.get_allocated_amount(db, ref_type="DIRECT_PURCHASE", ref_id=purchase.id)
        if purchase.total > paid:
            options.append(
                SupplierPaymentBillOption(
                    ref_type="DIRECT_PURCHASE",
                    ref_id=purchase.id,
                    doc_no=purchase.doc_no,
                    doc_date=purchase.doc_date,
                    total=purchase.total,
                    paid=paid,
                    outstanding=purchase.total - paid,
                )
            )
    return options


def _snapshot(payment: SupplierPayment) -> dict[str, object]:
    return {
        "doc_no": payment.doc_no,
        "doc_date": payment.doc_date.isoformat(),
        "supplier_id": payment.supplier_id,
        "account_id": payment.account_id,
        "amount": str(payment.amount),
        "status": payment.status,
        "note": payment.note,
        "allocations": [
            {
                "ref_type": item.ref_type,
                "ref_id": item.ref_id,
                "amount": str(item.amount),
            }
            for item in payment.allocations
        ],
    }


def due_entry_data(payment: SupplierPayment) -> dict[str, object]:
    return {
        "date": payment.doc_date.isoformat(),
        "type": "SUPPLIER_PAYMENT",
        "description": f"Supplier Payment {payment.doc_no}",
        "amount": -payment.amount,
    }
