from sqlalchemy import select
from sqlalchemy.orm import Session, lazyload, selectinload

from app.modules.goods_receipts.models import GoodsReceipt, GoodsReceiptLine
from app.modules.purchase_orders.models import PurchaseOrder, PurchaseOrderLine


def list_receipts(db: Session, *, offset: int = 0, limit: int = 50) -> list[GoodsReceipt]:
    statement = (
        select(GoodsReceipt)
        .options(selectinload(GoodsReceipt.lines))
        .order_by(GoodsReceipt.doc_date.desc(), GoodsReceipt.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(statement))


def get_receipt(db: Session, receipt_id: int) -> GoodsReceipt | None:
    statement = (
        select(GoodsReceipt)
        .options(selectinload(GoodsReceipt.lines))
        .where(GoodsReceipt.id == receipt_id)
    )
    return db.scalar(statement)


def get_order_for_update(db: Session, po_id: int) -> PurchaseOrder | None:
    statement = select(PurchaseOrder).where(PurchaseOrder.id == po_id).with_for_update()
    return db.scalar(statement)


def list_order_lines_for_update(db: Session, po_id: int) -> list[PurchaseOrderLine]:
    statement = (
        select(PurchaseOrderLine)
        .where(PurchaseOrderLine.po_id == po_id)
        .order_by(PurchaseOrderLine.id)
        .with_for_update()
    )
    return list(db.scalars(statement))


def get_receipt_for_update(db: Session, receipt_id: int) -> GoodsReceipt | None:
    statement = select(GoodsReceipt).where(GoodsReceipt.id == receipt_id).with_for_update()
    return db.scalar(statement)


def list_receipt_lines_for_update(db: Session, receipt_id: int) -> list[GoodsReceiptLine]:
    statement = (
        select(GoodsReceiptLine)
        .options(lazyload(GoodsReceiptLine.product))
        .where(GoodsReceiptLine.receipt_id == receipt_id)
        .order_by(GoodsReceiptLine.id)
        .with_for_update()
    )
    return list(db.scalars(statement))


def list_receipt_due_entries(db: Session, supplier_id: int) -> list[GoodsReceipt]:
    statement = (
        select(GoodsReceipt)
        .options(selectinload(GoodsReceipt.lines))
        .where(GoodsReceipt.supplier_id == supplier_id, GoodsReceipt.status == "POSTED")
        .order_by(GoodsReceipt.doc_date, GoodsReceipt.id)
    )
    return list(db.scalars(statement))


def list_receivable_orders(db: Session, *, limit: int = 200) -> list[PurchaseOrder]:
    statement = (
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.lines))
        .where(PurchaseOrder.status.in_(("APPROVED", "PARTIALLY_RECEIVED")))
        .order_by(PurchaseOrder.doc_date, PurchaseOrder.id)
        .limit(limit)
    )
    return list(db.scalars(statement))
