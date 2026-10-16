from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.quotations import service
from app.modules.quotations.models import Quotation
from app.modules.quotations.schemas import (
    QuotationCreate,
    QuotationOptionsResponse,
    QuotationResponse,
    QuotationUpdate,
)
from app.modules.sales_orders import service as sales_order_service
from app.modules.sales_orders.schemas import SalesOrderFromQuotationCreate, SalesOrderResponse

router = APIRouter(prefix="/api/v1/sales/quotations", tags=["quotations"])


@router.get("/options", response_model=QuotationOptionsResponse)
def get_quotation_options(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sales.quotations.read")),
) -> QuotationOptionsResponse:
    return service.get_quotation_options(db)


@router.get("", response_model=list[QuotationResponse])
def list_quotations(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sales.quotations.read")),
) -> list[Quotation]:
    return service.list_quotations(db, offset=offset, limit=limit)


@router.post("", response_model=QuotationResponse, status_code=status.HTTP_201_CREATED)
def create_quotation(
    payload: QuotationCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("sales.quotations.create")),
) -> Quotation:
    ip = request.client.host if request.client else None
    return service.create_quotation(db, payload, actor, ip)


@router.get("/{quotation_id}", response_model=QuotationResponse)
def get_quotation(
    quotation_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sales.quotations.read")),
) -> Quotation:
    quotation = service.get_quotation(db, quotation_id)
    if quotation is None:
        raise HTTPException(status_code=404, detail="Quotation not found")
    return quotation


@router.put("/{quotation_id}", response_model=QuotationResponse)
def update_quotation(
    quotation_id: int,
    payload: QuotationUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("sales.quotations.update")),
) -> Quotation:
    ip = request.client.host if request.client else None
    return service.update_quotation(db, quotation_id, payload, actor, ip)


@router.post("/{quotation_id}/send", response_model=QuotationResponse)
def send_quotation(
    quotation_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("sales.quotations.update")),
) -> Quotation:
    ip = request.client.host if request.client else None
    return service.transition_quotation(
        db, quotation_id=quotation_id, target_status="SENT", actor=actor, ip=ip
    )


@router.post("/{quotation_id}/accept", response_model=QuotationResponse)
def accept_quotation(
    quotation_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("sales.quotations.update")),
) -> Quotation:
    ip = request.client.host if request.client else None
    return service.transition_quotation(
        db, quotation_id=quotation_id, target_status="ACCEPTED", actor=actor, ip=ip
    )


@router.post("/{quotation_id}/reject", response_model=QuotationResponse)
def reject_quotation(
    quotation_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("sales.quotations.update")),
) -> Quotation:
    ip = request.client.host if request.client else None
    return service.transition_quotation(
        db, quotation_id=quotation_id, target_status="REJECTED", actor=actor, ip=ip
    )


@router.post(
    "/{quotation_id}/convert",
    response_model=SalesOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def convert_quotation(
    quotation_id: int,
    payload: SalesOrderFromQuotationCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("sales.orders.create")),
) -> SalesOrderResponse:
    ip = request.client.host if request.client else None
    order = sales_order_service.convert_accepted_quotation(
        db,
        quotation_id=quotation_id,
        payload=payload,
        actor=actor,
        ip=ip,
    )
    return sales_order_service.serialize_sales_order(db, order)
