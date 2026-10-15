from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.company_settings import repository as settings_repository
from app.modules.customers import repository as customer_repository
from app.modules.customers import service as customer_service
from app.modules.document_numbering.service import generate_next_number
from app.modules.sales.models import SalesDelivery
from app.modules.sales_invoices import repository
from app.modules.sales_invoices.models import SalesInvoice, SalesInvoiceLine
from app.modules.sales_invoices.schemas import (
    SalesInvoiceDeliveryOption,
    SalesInvoiceOptionsResponse,
)

DOCUMENT_TYPE = "INVOICE"
CENT = Decimal("0.01")
MAX_MONEY = Decimal("9999999999999999.99")


def list_invoices(db: Session, *, offset: int = 0, limit: int = 50) -> list[SalesInvoice]:
    return repository.list_invoices(db, offset=offset, limit=limit)


def get_invoice(db: Session, invoice_id: int) -> SalesInvoice | None:
    return repository.get_invoice(db, invoice_id)


def get_invoice_options(db: Session) -> SalesInvoiceOptionsResponse:
    return SalesInvoiceOptionsResponse(
        deliveries=[
            SalesInvoiceDeliveryOption(
                id=delivery.id,
                doc_no=delivery.doc_no,
                doc_date=delivery.doc_date,
                order_doc_no=delivery.sales_order.doc_no,
            )
            for delivery in repository.list_uninvoiced_deliveries(db)
        ]
    )


def create_invoice(
    db: Session,
    *,
    delivery_id: int,
    doc_date: date,
    due_date: date,
    actor: User,
    ip: str | None = None,
) -> tuple[SalesInvoice, bool]:
    try:
        if due_date < doc_date:
            raise HTTPException(status_code=422, detail="Due date cannot precede invoice date")

        customer_id = repository.get_delivery_customer_id_for_update(db, delivery_id)
        if customer_id is None:
            raise HTTPException(status_code=404, detail="Posted delivery not found")
        customer = customer_repository.get_customer_for_update(db, customer_id)
        if customer is None:
            raise HTTPException(status_code=404, detail="Customer not found")

        delivery = repository.get_delivery_for_update(db, delivery_id)
        if delivery is None or delivery.status != "POSTED":
            raise HTTPException(status_code=404, detail="Posted delivery not found")
        if delivery.invoice is not None:
            raise HTTPException(status_code=409, detail="DELIVERY_ALREADY_INVOICED")

        lines: list[SalesInvoiceLine] = []
        subtotal = Decimal("0.00")
        cogs_total = Decimal("0.00")
        for delivery_line in delivery.lines:
            unit_price = delivery_line.order_line.unit_price
            line_total = (delivery_line.qty * unit_price).quantize(CENT, rounding=ROUND_HALF_UP)
            line_cogs = (delivery_line.qty * delivery_line.unit_cost_cogs).quantize(
                CENT, rounding=ROUND_HALF_UP
            )
            subtotal += line_total
            cogs_total += line_cogs
            lines.append(
                SalesInvoiceLine(
                    product_id=delivery_line.product_id,
                    qty=delivery_line.qty,
                    unit_price=unit_price,
                    line_total=line_total,
                    unit_cost_cogs=delivery_line.unit_cost_cogs,
                )
            )

        if subtotal > MAX_MONEY or cogs_total > MAX_MONEY:
            raise HTTPException(status_code=422, detail="Invoice total exceeds supported amount")
        discount = _delivery_discount(db, delivery, subtotal)
        total = subtotal - discount
        if total > MAX_MONEY:
            raise HTTPException(status_code=422, detail="Invoice total exceeds supported amount")

        statement = customer_service.get_customer_statement(db, customer)
        current_due = Decimal(str(statement["balance"]))
        credit_warning = current_due + total > customer.credit_limit
        mode_setting = settings_repository.get_setting(db, "credit_limit_mode")
        credit_mode = mode_setting.value.upper() if mode_setting is not None else "WARN"
        if credit_mode not in {"WARN", "BLOCK"}:
            raise HTTPException(status_code=500, detail="Invalid credit limit mode setting")
        if credit_warning and credit_mode == "BLOCK":
            raise HTTPException(status_code=409, detail="CREDIT_LIMIT_EXCEEDED")

        invoice = SalesInvoice(
            doc_no=generate_next_number(db, DOCUMENT_TYPE, doc_date.year),
            doc_date=doc_date,
            due_date=due_date,
            customer_id=customer.id,
            delivery_id=delivery.id,
            status="POSTED",
            subtotal=subtotal,
            discount=discount,
            total=total,
            cogs_total=cogs_total,
            created_by=actor.id,
            lines=lines,
        )
        db.add(invoice)
        db.flush()
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="invoice",
            entity_id=invoice.id,
            action="CREATE",
            after=_snapshot(invoice),
            ip=ip,
        )
        db.commit()
        result = repository.get_invoice(db, invoice.id)
        if result is None:
            raise HTTPException(status_code=500, detail="Posted invoice could not be reloaded")
        return result, credit_warning
    except Exception:
        db.rollback()
        raise


def _delivery_discount(db: Session, delivery: SalesDelivery, subtotal: Decimal) -> Decimal:
    order = delivery.sales_order
    prior_invoices = repository.list_order_invoices(db, order.id)
    remaining_discount = max(
        Decimal("0.00"),
        order.discount - sum((invoice.discount for invoice in prior_invoices), Decimal("0.00")),
    )
    if not remaining_discount or not order.discount:
        return Decimal("0.00")
    fully_delivered = all(line.qty_delivered >= line.qty_ordered for line in order.lines)
    if not order.subtotal:
        return Decimal("0.00")
    if fully_delivered:
        return min(remaining_discount, subtotal)
    proportional = (subtotal * order.discount / order.subtotal).quantize(
        CENT, rounding=ROUND_HALF_UP
    )
    return min(remaining_discount, proportional, subtotal)


def list_customer_invoices(db: Session, customer_id: int) -> list[SalesInvoice]:
    return repository.list_customer_invoices(db, customer_id)


def due_entry_data(invoice: SalesInvoice) -> dict[str, object]:
    return {
        "date": invoice.doc_date.isoformat(),
        "type": "INVOICE",
        "description": f"Sales Invoice {invoice.doc_no}",
        "amount": invoice.total,
    }


def _snapshot(invoice: SalesInvoice) -> dict[str, object]:
    return {
        "doc_no": invoice.doc_no,
        "doc_date": invoice.doc_date.isoformat(),
        "due_date": invoice.due_date.isoformat(),
        "customer_id": invoice.customer_id,
        "delivery_id": invoice.delivery_id,
        "status": invoice.status,
        "subtotal": str(invoice.subtotal),
        "discount": str(invoice.discount),
        "total": str(invoice.total),
        "cogs_total": str(invoice.cogs_total),
        "lines": [
            {
                "product_id": line.product_id,
                "qty": str(line.qty),
                "unit_price": str(line.unit_price),
                "line_total": str(line.line_total),
                "unit_cost_cogs": str(line.unit_cost_cogs),
            }
            for line in invoice.lines
        ],
    }
