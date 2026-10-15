from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, localcontext

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.customers import repository as customer_repository
from app.modules.document_numbering.service import generate_next_number
from app.modules.inventory.models import MovementType
from app.modules.inventory.service import post_stock_movement
from app.modules.sales_invoices.models import SalesInvoice
from app.modules.sales_returns import repository
from app.modules.sales_returns.models import SalesReturn, SalesReturnLine
from app.modules.sales_returns.schemas import (
    SalesReturnCreate,
    SalesReturnInvoiceLineOption,
    SalesReturnInvoiceOption,
    SalesReturnOptionsResponse,
)

DOCUMENT_TYPE = "SALES_RETURN"
CENT = Decimal("0.01")
MAX_MONEY = Decimal("9999999999999999.99")


def list_sales_returns(db: Session, *, offset: int = 0, limit: int = 50) -> list[SalesReturn]:
    return repository.list_sales_returns(db, offset=offset, limit=limit)


def get_sales_return(db: Session, return_id: int) -> SalesReturn | None:
    return repository.get_sales_return(db, return_id)


def get_sales_return_options(db: Session) -> SalesReturnOptionsResponse:
    invoices = repository.list_returnable_invoices(db)
    prior_lines = repository.list_return_lines_by_invoice_ids(
        db, [invoice.id for invoice in invoices]
    )
    returned = {
        invoice_id: {
            line_id: (qty, amount)
            for line_id, qty, amount in invoice_returns
        }
        for invoice_id, invoice_returns in prior_lines.items()
    }
    options: list[SalesReturnInvoiceOption] = []
    for invoice in invoices:
        lines: list[SalesReturnInvoiceLineOption] = []
        for line in invoice.lines:
            qty_returned = returned.get(invoice.id, {}).get(
                line.id, (Decimal("0.000"), Decimal("0.00"))
            )[0]
            qty_available = line.qty - qty_returned
            if qty_available <= 0:
                continue
            lines.append(
                SalesReturnInvoiceLineOption(
                    invoice_line_id=line.id,
                    product_id=line.product_id,
                    product_sku=line.product.sku,
                    product_name=line.product.name,
                    unit_code=line.product.unit.code,
                    allow_decimal=line.product.unit.allow_decimal,
                    qty_invoiced=line.qty,
                    qty_returned=qty_returned,
                    qty_available=qty_available,
                    unit_price=line.unit_price,
                    unit_cost_cogs=line.unit_cost_cogs,
                )
            )
        if lines:
            options.append(
                SalesReturnInvoiceOption(
                    id=invoice.id,
                    doc_no=invoice.doc_no,
                    doc_date=invoice.doc_date,
                    lines=lines,
                )
            )
    return SalesReturnOptionsResponse(invoices=options)


def create_sales_return(
    db: Session,
    payload: SalesReturnCreate,
    actor: User,
    ip: str | None = None,
) -> SalesReturn:
    try:
        customer_id = repository.get_invoice_customer_id(db, payload.invoice_id)
        if customer_id is None:
            raise HTTPException(status_code=404, detail="Posted invoice not found")
        customer = customer_repository.get_customer_for_update(db, customer_id)
        if customer is None:
            raise HTTPException(status_code=404, detail="Customer not found")

        invoice = repository.get_invoice_for_return(db, payload.invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Posted invoice not found")
        invoice_lines = {line.id: line for line in invoice.lines}
        payload_line_ids = [line.invoice_line_id for line in payload.lines]
        if len(payload_line_ids) != len(set(payload_line_ids)):
            raise HTTPException(
                status_code=422, detail="An invoice line may appear only once per return"
            )
        if any(line_id not in invoice_lines for line_id in payload_line_ids):
            raise HTTPException(
                status_code=422, detail="Return line does not belong to the selected invoice"
            )

        previously_returned: dict[int, tuple[Decimal, Decimal]] = {}
        for line in repository.list_existing_return_lines(db, invoice.id):
            old_qty, old_total = previously_returned.get(
                line.invoice_line_id, (Decimal("0.000"), Decimal("0.00"))
            )
            previously_returned[line.invoice_line_id] = (
                old_qty + line.qty,
                old_total + line.line_total,
            )
        net_line_totals = _invoice_line_net_totals(invoice)
        return_lines: list[SalesReturnLine] = []
        total = Decimal("0.00")
        ordered_requests = sorted(
            payload.lines,
            key=lambda requested: (
                invoice_lines[requested.invoice_line_id].product_id,
                requested.invoice_line_id,
            ),
        )
        for requested in ordered_requests:
            invoice_line = invoice_lines[requested.invoice_line_id]
            qty_returned, amount_returned = previously_returned.get(
                invoice_line.id, (Decimal("0.000"), Decimal("0.00"))
            )
            qty_available = invoice_line.qty - qty_returned
            if requested.qty > qty_available:
                raise HTTPException(status_code=409, detail="SALES_RETURN_EXCEEDS_DELIVERED_QTY")
            remaining_value = net_line_totals[invoice_line.id] - amount_returned
            if requested.qty == qty_available:
                line_total = remaining_value
            else:
                with localcontext() as context:
                    context.prec = 40
                    line_total = (remaining_value * requested.qty / qty_available).quantize(
                        CENT, rounding=ROUND_HALF_UP
                    )
            if line_total < 0 or line_total > MAX_MONEY or total + line_total > MAX_MONEY:
                raise HTTPException(
                    status_code=422, detail="Sales return total exceeds supported amount"
                )
            total += line_total
            return_lines.append(
                SalesReturnLine(
                    invoice_line_id=invoice_line.id,
                    product_id=invoice_line.product_id,
                    qty=requested.qty,
                    unit_price=invoice_line.unit_price,
                    line_total=line_total,
                    unit_cost_cogs=invoice_line.unit_cost_cogs,
                )
            )

        sales_return = SalesReturn(
            doc_no=generate_next_number(db, DOCUMENT_TYPE, payload.doc_date.year),
            doc_date=payload.doc_date,
            invoice_id=invoice.id,
            customer_id=invoice.customer_id,
            warehouse_id=invoice.delivery.warehouse_id,
            status="POSTED",
            total=total,
            note=payload.note,
            created_by=actor.id,
            lines=return_lines,
        )
        db.add(sales_return)
        db.flush()
        for line in sales_return.lines:
            post_stock_movement(
                db,
                product_id=line.product_id,
                warehouse_id=sales_return.warehouse_id,
                movement_type=MovementType.SALE_RETURN,
                qty_signed=line.qty,
                unit_cost=line.unit_cost_cogs,
                actor=actor,
                source_type="SALES_RETURN",
                source_id=sales_return.id,
                source_line_id=line.id,
                note=sales_return.note,
                txn_date=datetime.combine(payload.doc_date, datetime.min.time(), tzinfo=UTC),
            )
        db.flush()
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="sales_return",
            entity_id=sales_return.id,
            action="CREATE",
            after=_snapshot(sales_return),
            ip=ip,
        )
        db.commit()
        return repository.get_sales_return(db, sales_return.id) or sales_return
    except Exception:
        db.rollback()
        raise


def list_customer_returns(db: Session, customer_id: int) -> list[SalesReturn]:
    return repository.list_customer_returns(db, customer_id)


def due_entry_data(sales_return: SalesReturn) -> dict[str, object]:
    return {
        "date": sales_return.doc_date.isoformat(),
        "type": "SALES_RETURN",
        "description": f"Sales Return {sales_return.doc_no}",
        "amount": -sales_return.total,
    }


def _invoice_line_net_totals(invoice: SalesInvoice) -> dict[int, Decimal]:
    remaining_discount = invoice.discount
    result: dict[int, Decimal] = {}
    for index, line in enumerate(invoice.lines):
        if invoice.subtotal <= 0 or remaining_discount <= 0:
            line_discount = Decimal("0.00")
        elif index == len(invoice.lines) - 1:
            line_discount = min(remaining_discount, line.line_total)
        else:
            line_discount = min(
                remaining_discount,
                line.line_total,
                (invoice.discount * line.line_total / invoice.subtotal).quantize(
                    CENT, rounding=ROUND_HALF_UP
                ),
            )
        remaining_discount -= line_discount
        result[line.id] = line.line_total - line_discount
    return result


def _snapshot(sales_return: SalesReturn) -> dict[str, object]:
    return {
        "doc_no": sales_return.doc_no,
        "doc_date": sales_return.doc_date.isoformat(),
        "invoice_id": sales_return.invoice_id,
        "customer_id": sales_return.customer_id,
        "warehouse_id": sales_return.warehouse_id,
        "status": sales_return.status,
        "total": str(sales_return.total),
        "note": sales_return.note,
        "lines": [
            {
                "invoice_line_id": line.invoice_line_id,
                "product_id": line.product_id,
                "qty": str(line.qty),
                "unit_price": str(line.unit_price),
                "line_total": str(line.line_total),
                "unit_cost_cogs": str(line.unit_cost_cogs),
            }
            for line in sales_return.lines
        ],
    }
