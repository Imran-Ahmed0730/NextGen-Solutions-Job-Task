from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.direct_purchases.models import DirectPurchase
from app.modules.goods_receipts.models import GoodsReceipt
from app.modules.purchase_returns.models import PurchaseReturn
from app.modules.supplier_payments.models import SupplierPayment, SupplierPaymentAllocation
from app.modules.suppliers.models import Supplier


def list_payments(db: Session, *, offset: int, limit: int) -> list[SupplierPayment]:
    statement = (
        select(SupplierPayment)
        .order_by(SupplierPayment.doc_date.desc(), SupplierPayment.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(statement))


def get_supplier_for_update(db: Session, supplier_id: int) -> Supplier | None:
    return db.scalar(
        select(Supplier)
        .where(Supplier.id == supplier_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def list_supplier_payments(db: Session, supplier_id: int) -> list[SupplierPayment]:
    return list(
        db.scalars(
            select(SupplierPayment)
            .where(SupplierPayment.supplier_id == supplier_id)
            .order_by(SupplierPayment.doc_date, SupplierPayment.id)
        )
    )


def get_receipt_for_update(db: Session, receipt_id: int) -> GoodsReceipt | None:
    return db.scalar(
        select(GoodsReceipt)
        .where(GoodsReceipt.id == receipt_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def get_direct_purchase_for_update(db: Session, purchase_id: int) -> DirectPurchase | None:
    return db.scalar(
        select(DirectPurchase)
        .where(DirectPurchase.id == purchase_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def get_allocated_amount(
    db: Session, *, ref_type: str, ref_id: int, for_update: bool = False
) -> Decimal:
    statement = select(SupplierPaymentAllocation.amount).where(
        SupplierPaymentAllocation.ref_type == ref_type,
        SupplierPaymentAllocation.ref_id == ref_id,
    )
    if for_update:
        statement = statement.with_for_update()
        amounts = db.scalars(statement)
        return sum(amounts, Decimal("0.00"))
    return db.scalar(
        select(func.sum(SupplierPaymentAllocation.amount)).where(
            SupplierPaymentAllocation.ref_type == ref_type,
            SupplierPaymentAllocation.ref_id == ref_id,
        )
    ) or Decimal("0.00")


def get_returned_receipt_amount(db: Session, receipt_id: int) -> Decimal:
    return db.scalar(
        select(func.sum(PurchaseReturn.total)).where(PurchaseReturn.receipt_id == receipt_id)
    ) or Decimal("0.00")


def list_receipt_bills(db: Session, supplier_id: int) -> list[GoodsReceipt]:
    return list(
        db.scalars(
            select(GoodsReceipt)
            .where(GoodsReceipt.supplier_id == supplier_id, GoodsReceipt.status == "POSTED")
            .order_by(GoodsReceipt.doc_date, GoodsReceipt.id)
        )
    )


def list_direct_purchase_bills(db: Session, supplier_id: int) -> list[DirectPurchase]:
    return list(
        db.scalars(
            select(DirectPurchase)
            .where(DirectPurchase.supplier_id == supplier_id, DirectPurchase.status == "POSTED")
            .order_by(DirectPurchase.doc_date, DirectPurchase.id)
        )
    )
