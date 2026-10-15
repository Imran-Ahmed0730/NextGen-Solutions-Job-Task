from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.modules.products.models import Product
from app.modules.sales_invoices.models import SalesInvoice, SalesInvoiceLine
from app.modules.sales_returns.models import SalesReturn, SalesReturnLine


def list_sales_returns(db: Session, *, offset: int = 0, limit: int = 50) -> list[SalesReturn]:
    statement = (
        select(SalesReturn)
        .options(selectinload(SalesReturn.lines))
        .order_by(SalesReturn.doc_date.desc(), SalesReturn.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(statement))


def get_sales_return(db: Session, return_id: int) -> SalesReturn | None:
    statement = (
        select(SalesReturn)
        .options(selectinload(SalesReturn.lines))
        .where(SalesReturn.id == return_id)
    )
    return db.scalar(statement)


def get_invoice_customer_id(db: Session, invoice_id: int) -> int | None:
    return db.scalar(select(SalesInvoice.customer_id).where(SalesInvoice.id == invoice_id))


def get_invoice_for_return(db: Session, invoice_id: int) -> SalesInvoice | None:
    statement = (
        select(SalesInvoice)
        .options(
            selectinload(SalesInvoice.lines).joinedload(SalesInvoiceLine.product),
            joinedload(SalesInvoice.delivery),
        )
        .where(SalesInvoice.id == invoice_id, SalesInvoice.status == "POSTED")
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return db.scalar(statement)


def list_returnable_invoices(db: Session, *, limit: int = 200) -> list[SalesInvoice]:
    statement = (
        select(SalesInvoice)
        .options(
            selectinload(SalesInvoice.lines).joinedload(SalesInvoiceLine.product).joinedload(
                Product.unit
            ),
            joinedload(SalesInvoice.delivery),
        )
        .where(SalesInvoice.status == "POSTED")
        .order_by(SalesInvoice.doc_date.desc(), SalesInvoice.id.desc())
        .limit(limit)
    )
    return list(db.scalars(statement))


def list_existing_return_lines(db: Session, invoice_id: int) -> list[SalesReturnLine]:
    statement = (
        select(SalesReturnLine)
        .join(SalesReturn, SalesReturn.id == SalesReturnLine.return_id)
        .where(SalesReturn.invoice_id == invoice_id, SalesReturn.status == "POSTED")
        .order_by(SalesReturnLine.id)
    )
    return list(db.scalars(statement))


def list_return_lines_by_invoice_ids(
    db: Session, invoice_ids: Sequence[int]
) -> dict[int, list[tuple[int, Decimal, Decimal]]]:
    if not invoice_ids:
        return {}
    statement = (
        select(SalesReturn.invoice_id, SalesReturnLine.invoice_line_id,
               func.sum(SalesReturnLine.qty), func.sum(SalesReturnLine.line_total))
        .join(SalesReturnLine, SalesReturnLine.return_id == SalesReturn.id)
        .where(SalesReturn.invoice_id.in_(invoice_ids), SalesReturn.status == "POSTED")
        .group_by(SalesReturn.invoice_id, SalesReturnLine.invoice_line_id)
    )
    result: dict[int, list[tuple[int, Decimal, Decimal]]] = {}
    for invoice_id, line_id, qty, amount in db.execute(statement):
        result.setdefault(invoice_id, []).append((line_id, qty, amount))
    return result


def list_customer_returns(db: Session, customer_id: int) -> list[SalesReturn]:
    statement = (
        select(SalesReturn)
        .where(SalesReturn.customer_id == customer_id, SalesReturn.status == "POSTED")
        .order_by(SalesReturn.doc_date, SalesReturn.id)
    )
    return list(db.scalars(statement))
