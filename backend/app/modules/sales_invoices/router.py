from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.sales_invoices import service
from app.modules.sales_invoices.models import SalesInvoice
from app.modules.sales_invoices.schemas import (
    SalesInvoiceCreate,
    SalesInvoiceCreateResponse,
    SalesInvoiceOptionsResponse,
    SalesInvoiceResponse,
)

router = APIRouter(prefix="/api/v1/sales/invoices", tags=["sales-invoices"])


@router.get("/options", response_model=SalesInvoiceOptionsResponse)
def get_invoice_options(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sales.invoices.read")),
) -> SalesInvoiceOptionsResponse:
    return service.get_invoice_options(db)


@router.get("", response_model=list[SalesInvoiceResponse])
def list_invoices(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sales.invoices.read")),
) -> list[SalesInvoice]:
    return service.list_invoices(db, offset=offset, limit=limit)


@router.post(
    "",
    response_model=SalesInvoiceCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_invoice(
    payload: SalesInvoiceCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("sales.invoices.create")),
) -> SalesInvoiceCreateResponse:
    ip = request.client.host if request.client else None
    invoice, credit_limit_warning = service.create_invoice(
        db,
        delivery_id=payload.delivery_id,
        doc_date=payload.doc_date,
        due_date=payload.due_date,
        actor=actor,
        ip=ip,
    )
    return SalesInvoiceCreateResponse(
        invoice=SalesInvoiceResponse.model_validate(invoice),
        credit_limit_warning=credit_limit_warning,
    )


@router.get("/{invoice_id}", response_model=SalesInvoiceResponse)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sales.invoices.read")),
) -> SalesInvoice:
    invoice = service.get_invoice(db, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice
