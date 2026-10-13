from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.payment_methods import service
from app.modules.payment_methods.models import PaymentMethod
from app.modules.payment_methods.schemas import (
    PaymentMethodCreate,
    PaymentMethodResponse,
    PaymentMethodUpdate,
)

router = APIRouter(prefix="/api/v1/payment-methods", tags=["payment-methods"])


def _payment_method_or_404(db: Session, payment_method_id: int) -> PaymentMethod:
    payment_method = service.get_payment_method(db, payment_method_id)
    if payment_method is None:
        raise HTTPException(status_code=404, detail="Payment method not found")
    return payment_method


@router.get("", response_model=list[PaymentMethodResponse])
def list_payment_methods(
    include_inactive: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master_data.payment_methods.read")),
) -> list[PaymentMethod]:
    return service.list_payment_methods(
        db, include_inactive=include_inactive, offset=offset, limit=limit
    )


@router.post("", response_model=PaymentMethodResponse, status_code=status.HTTP_201_CREATED)
def create_payment_method(
    payload: PaymentMethodCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.payment_methods.create")),
) -> PaymentMethod:
    return service.create_payment_method(db, payload.model_dump(), actor, _ip(request))


@router.get("/{payment_method_id}", response_model=PaymentMethodResponse)
def get_payment_method(
    payment_method_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master_data.payment_methods.read")),
) -> PaymentMethod:
    return _payment_method_or_404(db, payment_method_id)


@router.patch("/{payment_method_id}", response_model=PaymentMethodResponse)
def update_payment_method(
    payment_method_id: int,
    payload: PaymentMethodUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.payment_methods.update")),
) -> PaymentMethod:
    payment_method = _payment_method_or_404(db, payment_method_id)
    return service.update_payment_method(
        db, payment_method, payload.model_dump(exclude_unset=True), actor, _ip(request)
    )


@router.delete("/{payment_method_id}", response_model=PaymentMethodResponse)
def delete_payment_method(
    payment_method_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.payment_methods.delete")),
) -> PaymentMethod:
    return service.delete_payment_method(
        db, _payment_method_or_404(db, payment_method_id), actor, _ip(request)
    )


@router.post("/{payment_method_id}/activate", response_model=PaymentMethodResponse)
def activate_payment_method(
    payment_method_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.payment_methods.update")),
) -> PaymentMethod:
    return service.activate_payment_method(
        db, _payment_method_or_404(db, payment_method_id), actor, _ip(request)
    )


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None