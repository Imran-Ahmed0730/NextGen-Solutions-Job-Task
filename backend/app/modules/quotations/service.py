from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.customers import service as customer_service
from app.modules.document_numbering.service import generate_next_number
from app.modules.products import service as product_service
from app.modules.quotations import repository
from app.modules.quotations.models import Quotation, QuotationLine
from app.modules.quotations.schemas import (
    QuotationCreate,
    QuotationCustomerOption,
    QuotationOptionsResponse,
    QuotationProductOption,
    QuotationUpdate,
)

DOCUMENT_TYPE = "QUOTATION"
CENT = Decimal("0.01")


def list_quotations(db: Session, *, offset: int = 0, limit: int = 50) -> list[Quotation]:
    return repository.list_quotations(db, offset=offset, limit=limit)


def get_quotation(db: Session, quotation_id: int) -> Quotation | None:
    return repository.get_quotation(db, quotation_id)


def get_quotation_options(db: Session) -> QuotationOptionsResponse:
    customers = customer_service.list_customers(db, limit=200)
    products = product_service.list_products(db, limit=200)
    return QuotationOptionsResponse(
        customers=[
            QuotationCustomerOption(id=item.id, code=item.code, name=item.name)
            for item in customers
        ],
        products=[
            QuotationProductOption(
                id=item.id,
                sku=item.sku,
                name=item.name,
                unit_code=item.unit.code,
                allow_decimal=item.unit.allow_decimal,
            )
            for item in products
        ],
    )


def create_quotation(
    db: Session,
    payload: QuotationCreate,
    actor: User,
    ip: str | None = None,
) -> Quotation:
    try:
        customer = customer_service.get_customer(db, payload.customer_id)
        if customer is None or not customer.is_active or customer.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Customer not found")
        _validate_products(db, payload)
        lines, subtotal, discount, total = _build_lines(payload)
        quotation = Quotation(
            doc_no=generate_next_number(db, DOCUMENT_TYPE, payload.doc_date.year),
            doc_date=payload.doc_date,
            customer_id=customer.id,
            valid_until=payload.valid_until,
            status="DRAFT",
            subtotal=subtotal,
            discount=discount,
            total=total,
            note=payload.note,
            created_by=actor.id,
            lines=lines,
        )
        db.add(quotation)
        db.flush()
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="quotation",
            entity_id=quotation.id,
            action="CREATE",
            after=_snapshot(quotation),
            ip=ip,
        )
        db.commit()
        return repository.get_quotation(db, quotation.id) or quotation
    except Exception:
        db.rollback()
        raise


def update_quotation(
    db: Session,
    quotation_id: int,
    payload: QuotationUpdate,
    actor: User,
    ip: str | None = None,
) -> Quotation:
    try:
        quotation = repository.get_quotation(db, quotation_id, for_update=True)
        if quotation is None:
            raise HTTPException(status_code=404, detail="Quotation not found")
        if quotation.status != "DRAFT":
            raise HTTPException(status_code=409, detail="QUOTATION_NOT_EDITABLE")
        if payload.doc_date.year != quotation.doc_date.year:
            raise HTTPException(
                status_code=422, detail="Document date year cannot change after numbering"
            )
        customer = customer_service.get_customer(db, payload.customer_id)
        if customer is None or not customer.is_active or customer.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Customer not found")
        _validate_products(db, payload)
        lines, subtotal, discount, total = _build_lines(payload)

        before = _snapshot(quotation)
        quotation.doc_date = payload.doc_date
        quotation.customer_id = customer.id
        quotation.valid_until = payload.valid_until
        quotation.subtotal = subtotal
        quotation.discount = discount
        quotation.total = total
        quotation.note = payload.note
        quotation.lines = lines
        quotation.updated_at = datetime.now(UTC)
        db.flush()
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="quotation",
            entity_id=quotation.id,
            action="UPDATE",
            before=before,
            after=_snapshot(quotation),
            ip=ip,
        )
        db.commit()
        return repository.get_quotation(db, quotation.id) or quotation
    except Exception:
        db.rollback()
        raise


def _validate_products(db: Session, payload: QuotationCreate | QuotationUpdate) -> None:
    for line in payload.lines:
        product = product_service.get_product(db, line.product_id)
        if product is None or not product.is_active or product.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Product not found")


def _build_lines(
    payload: QuotationCreate | QuotationUpdate,
) -> tuple[list[QuotationLine], Decimal, Decimal, Decimal]:
    lines: list[QuotationLine] = []
    subtotal = Decimal("0.00")
    for line in payload.lines:
        line_total = (line.qty * line.unit_price).quantize(CENT, rounding=ROUND_HALF_UP)
        subtotal += line_total
        lines.append(
            QuotationLine(
                product_id=line.product_id,
                qty=line.qty,
                unit_price=line.unit_price,
                line_total=line_total,
            )
        )
    if payload.discount > subtotal:
        raise HTTPException(status_code=422, detail="Discount cannot exceed the subtotal")
    return lines, subtotal, payload.discount, subtotal - payload.discount


def _snapshot(quotation: Quotation) -> dict[str, object]:
    return {
        "doc_no": quotation.doc_no,
        "doc_date": quotation.doc_date.isoformat(),
        "customer_id": quotation.customer_id,
        "valid_until": quotation.valid_until.isoformat() if quotation.valid_until else None,
        "status": quotation.status,
        "subtotal": str(quotation.subtotal),
        "discount": str(quotation.discount),
        "total": str(quotation.total),
        "note": quotation.note,
        "lines": [
            {
                "product_id": line.product_id,
                "qty": str(line.qty),
                "unit_price": str(line.unit_price),
                "line_total": str(line.line_total),
            }
            for line in quotation.lines
        ],
    }
