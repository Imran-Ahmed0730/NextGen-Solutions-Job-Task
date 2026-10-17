from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.customers import repository, service
from app.modules.customers.models import Customer
from app.modules.customers.schemas import (
    ContactCreate,
    ContactResponse,
    ContactUpdate,
    CustomerCreate,
    CustomerResponse,
    CustomerUpdate,
)
from app.modules.parties import repository as party_repository
from app.modules.parties.models import PartyContact

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


def _customer_or_404(db: Session, customer_id: int) -> Customer:
    customer = service.get_customer(db, customer_id)
    if customer is None or customer.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.get("", response_model=list[CustomerResponse])
def list_customers(
    include_inactive: bool = False,
    search: str | None = Query(default=None, max_length=100),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master_data.customers.read")),
) -> list[Customer]:
    return service.list_customers(
        db, include_inactive=include_inactive, offset=offset, limit=limit, search=search
    )


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.customers.create")),
) -> Customer:
    return service.create_customer(db, payload.model_dump(), actor, _ip(request))


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master_data.customers.read")),
) -> Customer:
    return _customer_or_404(db, customer_id)


@router.patch("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: int,
    payload: CustomerUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.customers.update")),
) -> Customer:
    customer = _customer_or_404(db, customer_id)
    return service.update_customer(
        db, customer, payload.model_dump(exclude_unset=True), actor, _ip(request)
    )


@router.delete("/{customer_id}", response_model=CustomerResponse)
def delete_customer(
    customer_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.customers.delete")),
) -> Customer:
    customer = _customer_or_404(db, customer_id)
    return service.delete_customer(db, customer, actor, _ip(request))


@router.post("/{customer_id}/activate", response_model=CustomerResponse)
def activate_customer(
    customer_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.customers.update")),
) -> Customer:
    customer = repository.get_customer(db, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return service.activate_customer(db, customer, actor, _ip(request))


@router.get("/{customer_id}/statement")
def customer_statement(
    customer_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master_data.customers.read")),
) -> dict[str, object]:
    customer = _customer_or_404(db, customer_id)
    return service.get_customer_statement(db, customer)


@router.get("/{customer_id}/contacts", response_model=list[ContactResponse])
def list_contacts(
    customer_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master_data.customers.read")),
) -> list[PartyContact]:
    _customer_or_404(db, customer_id)
    return service.list_contacts(db, customer_id)


@router.post(
    "/{customer_id}/contacts",
    response_model=ContactResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_contact(
    customer_id: int,
    payload: ContactCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.customers.create")),
) -> PartyContact:
    customer = _customer_or_404(db, customer_id)
    return service.create_contact(db, customer.id, payload.model_dump(), actor, _ip(request))


@router.patch("/{customer_id}/contacts/{contact_id}", response_model=ContactResponse)
def update_contact(
    customer_id: int,
    contact_id: int,
    payload: ContactUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.customers.update")),
) -> PartyContact:
    _customer_or_404(db, customer_id)
    contact = party_repository.get_contact(db, contact_id)
    if contact is None or contact.party_type != "CUSTOMER" or contact.party_id != customer_id:
        raise HTTPException(status_code=404, detail="Contact not found")
    return service.update_contact(
        db, contact, payload.model_dump(exclude_unset=True), actor, _ip(request)
    )


@router.delete("/{customer_id}/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(
    customer_id: int,
    contact_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.customers.delete")),
) -> None:
    _customer_or_404(db, customer_id)
    contact = party_repository.get_contact(db, contact_id)
    if contact is None or contact.party_type != "CUSTOMER" or contact.party_id != customer_id:
        raise HTTPException(status_code=404, detail="Contact not found")
    service.delete_contact(db, contact, actor, _ip(request))


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None
