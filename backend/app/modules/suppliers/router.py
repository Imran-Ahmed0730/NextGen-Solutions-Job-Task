from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.parties import repository as party_repository
from app.modules.parties.models import PartyContact
from app.modules.suppliers import repository, service
from app.modules.suppliers.models import Supplier
from app.modules.suppliers.schemas import (
    ContactCreate,
    ContactResponse,
    ContactUpdate,
    SupplierCreate,
    SupplierResponse,
    SupplierUpdate,
)

router = APIRouter(prefix="/api/v1/suppliers", tags=["suppliers"])


def _supplier_or_404(db: Session, supplier_id: int) -> Supplier:
    supplier = service.get_supplier(db, supplier_id)
    if supplier is None or supplier.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


@router.get("", response_model=list[SupplierResponse])
def list_suppliers(
    include_inactive: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master_data.suppliers.read")),
) -> list[Supplier]:
    return service.list_suppliers(
        db, include_inactive=include_inactive, offset=offset, limit=limit
    )


@router.post("", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
def create_supplier(
    payload: SupplierCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.suppliers.create")),
) -> Supplier:
    return service.create_supplier(db, payload.model_dump(), actor, _ip(request))


@router.get("/{supplier_id}", response_model=SupplierResponse)
def get_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master_data.suppliers.read")),
) -> Supplier:
    return _supplier_or_404(db, supplier_id)


@router.patch("/{supplier_id}", response_model=SupplierResponse)
def update_supplier(
    supplier_id: int,
    payload: SupplierUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.suppliers.update")),
) -> Supplier:
    supplier = _supplier_or_404(db, supplier_id)
    return service.update_supplier(
        db, supplier, payload.model_dump(exclude_unset=True), actor, _ip(request)
    )


@router.delete("/{supplier_id}", response_model=SupplierResponse)
def delete_supplier(
    supplier_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.suppliers.delete")),
) -> Supplier:
    supplier = _supplier_or_404(db, supplier_id)
    return service.delete_supplier(db, supplier, actor, _ip(request))


@router.post("/{supplier_id}/activate", response_model=SupplierResponse)
def activate_supplier(
    supplier_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.suppliers.update")),
) -> Supplier:
    supplier = repository.get_supplier(db, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return service.activate_supplier(db, supplier, actor, _ip(request))


@router.get("/{supplier_id}/statement")
def supplier_statement(
    supplier_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master_data.suppliers.read")),
):
    supplier = _supplier_or_404(db, supplier_id)
    return service.get_supplier_statement(db, supplier)


@router.get("/{supplier_id}/contacts", response_model=list[ContactResponse])
def list_contacts(
    supplier_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master_data.suppliers.read")),
) -> list[PartyContact]:
    _supplier_or_404(db, supplier_id)
    return service.list_contacts(db, supplier_id)


@router.post(
    "/{supplier_id}/contacts",
    response_model=ContactResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_contact(
    supplier_id: int,
    payload: ContactCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.suppliers.create")),
) -> PartyContact:
    supplier = _supplier_or_404(db, supplier_id)
    return service.create_contact(db, supplier.id, payload.model_dump(), actor, _ip(request))


@router.patch("/{supplier_id}/contacts/{contact_id}", response_model=ContactResponse)
def update_contact(
    supplier_id: int,
    contact_id: int,
    payload: ContactUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.suppliers.update")),
) -> PartyContact:
    _supplier_or_404(db, supplier_id)
    contact = party_repository.get_contact(db, contact_id)
    if contact is None or contact.party_type != "SUPPLIER" or contact.party_id != supplier_id:
        raise HTTPException(status_code=404, detail="Contact not found")
    return service.update_contact(
        db, contact, payload.model_dump(exclude_unset=True), actor, _ip(request)
    )


@router.delete("/{supplier_id}/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(
    supplier_id: int,
    contact_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.suppliers.delete")),
) -> None:
    _supplier_or_404(db, supplier_id)
    contact = party_repository.get_contact(db, contact_id)
    if contact is None or contact.party_type != "SUPPLIER" or contact.party_id != supplier_id:
        raise HTTPException(status_code=404, detail="Contact not found")
    service.delete_contact(db, contact, actor, _ip(request))


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None