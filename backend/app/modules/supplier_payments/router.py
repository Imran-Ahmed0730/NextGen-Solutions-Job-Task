from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.supplier_payments import service
from app.modules.supplier_payments.models import SupplierPayment
from app.modules.supplier_payments.schemas import (
    SupplierPaymentBillOption,
    SupplierPaymentCreate,
    SupplierPaymentOptionsResponse,
    SupplierPaymentResponse,
)

router = APIRouter(prefix="/api/v1/money/supplier-payments", tags=["supplier-payments"])


@router.get("/options", response_model=SupplierPaymentOptionsResponse)
def get_payment_options(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("money.supplier_payments.read")),
) -> SupplierPaymentOptionsResponse:
    return service.get_payment_options(db)


@router.get("/bills", response_model=list[SupplierPaymentBillOption])
def list_bill_options(
    supplier_id: int = Query(ge=1),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("money.supplier_payments.read")),
) -> list[SupplierPaymentBillOption]:
    return service.list_bill_options(db, supplier_id)


@router.get("", response_model=list[SupplierPaymentResponse])
def list_payments(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("money.supplier_payments.read")),
) -> list[SupplierPayment]:
    return service.list_payments(db, offset=offset, limit=limit)


@router.post("", response_model=SupplierPaymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment(
    payload: SupplierPaymentCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("money.supplier_payments.create")),
) -> SupplierPayment:
    ip = request.client.host if request.client else None
    return service.create_payment(db, payload, actor, ip)
