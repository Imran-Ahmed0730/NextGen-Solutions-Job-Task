from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.modules.sales.models import SalesDelivery, SalesDeliveryLine, SalesOrder
from app.modules.sales_invoices.models import SalesInvoice


def get_delivery_customer_id_for_update(db: Session, delivery_id: int) -> int | None:
    statement = (
        select(SalesDelivery.customer_id).where(SalesDelivery.id == delivery_id).with_for_update()
    )
    return db.scalar(statement)


def list_invoices(db: Session, *, offset: int = 0, limit: int = 50) -> list[SalesInvoice]:
    statement = (
        select(SalesInvoice)
        .options(selectinload(SalesInvoice.lines))
        .order_by(SalesInvoice.doc_date.desc(), SalesInvoice.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(statement))


def get_invoice(db: Session, invoice_id: int) -> SalesInvoice | None:
    statement = (
        select(SalesInvoice)
        .options(selectinload(SalesInvoice.lines))
        .where(SalesInvoice.id == invoice_id)
    )
    return db.scalar(statement)


def get_delivery_for_update(db: Session, delivery_id: int) -> SalesDelivery | None:
    statement = (
        select(SalesDelivery)
        .options(
            selectinload(SalesDelivery.lines).selectinload(SalesDeliveryLine.order_line),
            selectinload(SalesDelivery.sales_order).selectinload(SalesOrder.lines),
        )
        .where(SalesDelivery.id == delivery_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return db.scalar(statement)


def list_uninvoiced_deliveries(db: Session, *, limit: int = 200) -> list[SalesDelivery]:
    statement = (
        select(SalesDelivery)
        .options(selectinload(SalesDelivery.sales_order))
        .outerjoin(SalesInvoice, SalesInvoice.delivery_id == SalesDelivery.id)
        .where(SalesInvoice.id.is_(None))
        .order_by(SalesDelivery.doc_date.desc(), SalesDelivery.id.desc())
        .limit(limit)
    )
    return list(db.scalars(statement))


def list_order_invoices(db: Session, order_id: int) -> list[SalesInvoice]:
    statement = (
        select(SalesInvoice)
        .join(SalesDelivery, SalesDelivery.id == SalesInvoice.delivery_id)
        .where(SalesDelivery.order_id == order_id)
        .order_by(SalesInvoice.id)
    )
    return list(db.scalars(statement))


def list_customer_invoices(db: Session, customer_id: int) -> list[SalesInvoice]:
    statement = (
        select(SalesInvoice)
        .where(SalesInvoice.customer_id == customer_id, SalesInvoice.status == "POSTED")
        .order_by(SalesInvoice.doc_date, SalesInvoice.id)
    )
    return list(db.scalars(statement))
