from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.parties import repository as party_repository
from app.modules.parties.models import PartyContact
from app.modules.suppliers import repository
from app.modules.suppliers.models import Supplier


def list_suppliers(
    db: Session,
    *,
    include_inactive: bool = False,
    offset: int = 0,
    limit: int = 50,
    search: str | None = None,
) -> list[Supplier]:
    return repository.list_suppliers(
        db, include_inactive=include_inactive, offset=offset, limit=limit, search=search
    )


def get_supplier(db: Session, supplier_id: int) -> Supplier | None:
    return repository.get_supplier(db, supplier_id)


def _validate_code(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=422, detail="Supplier code is required")
    code = value.strip()
    if len(code) > 30:
        raise HTTPException(status_code=422, detail="Supplier code is too long")
    return code


def _validate_name(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=422, detail="Supplier name is required")
    name = value.strip()
    if len(name) > 255:
        raise HTTPException(status_code=422, detail="Supplier name is too long")
    return name


def _validate_mobile(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise HTTPException(status_code=422, detail="Supplier mobile must be text")
    mobile = value.strip()
    if not mobile:
        return None
    if len(mobile) > 30:
        raise HTTPException(status_code=422, detail="Supplier mobile is too long")
    return mobile


def _validate_email(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise HTTPException(status_code=422, detail="Supplier email must be text")
    email = value.strip()
    if not email:
        return None
    if len(email) > 255:
        raise HTTPException(status_code=422, detail="Supplier email is too long")
    return email


def _validate_address(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise HTTPException(status_code=422, detail="Supplier address must be text")
    address = value.strip()
    if not address:
        return None
    return address


def _validate_decimal(value: object, field_name: str) -> Decimal:
    if value is None:
        return Decimal("0.00")
    if isinstance(value, bool):
        raise HTTPException(status_code=422, detail=f"{field_name} must be a number")
    try:
        number = Decimal(str(value))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"{field_name} must be a number") from exc
    if number < 0:
        raise HTTPException(status_code=422, detail=f"{field_name} cannot be negative")
    return number


def _validate_is_active(value: object) -> bool:
    if not isinstance(value, bool):
        raise HTTPException(status_code=422, detail="is_active must be a boolean")
    return value


def _ensure_code_available(db: Session, code: str, *, exclude_id: int | None = None) -> None:
    existing = repository.get_supplier_by_code(db, code)
    if existing is not None and existing.id != exclude_id:
        raise HTTPException(status_code=409, detail="Supplier code is already in use")


def create_supplier(
    db: Session, data: dict[str, object], actor: User, ip: str | None = None
) -> Supplier:
    code = _validate_code(data.get("code"))
    name = _validate_name(data.get("name"))
    mobile = _validate_mobile(data.get("mobile"))
    email = _validate_email(data.get("email"))
    address = _validate_address(data.get("address"))
    opening_due = _validate_decimal(data.get("opening_due", Decimal("0.00")), "Opening due")
    is_active = _validate_is_active(data.get("is_active", True))

    _ensure_code_available(db, code)

    supplier = Supplier(
        code=code,
        name=name,
        mobile=mobile,
        email=email,
        address=address,
        opening_due=opening_due,
        is_active=is_active,
    )
    db.add(supplier)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Supplier code is already in use") from exc

    record_audit(
        db,
        actor_id=actor.id,
        entity_type="supplier",
        entity_id=supplier.id,
        action="CREATE",
        after=_snapshot(supplier),
        ip=ip,
    )
    db.commit()
    db.refresh(supplier)
    return supplier


def update_supplier(
    db: Session,
    supplier: Supplier,
    data: dict[str, object],
    actor: User,
    ip: str | None = None,
) -> Supplier:
    if supplier.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Supplier not found")

    code = supplier.code
    if "code" in data:
        code = _validate_code(data["code"])
        if code != supplier.code:
            _ensure_code_available(db, code, exclude_id=supplier.id)

    name = supplier.name
    if "name" in data:
        name = _validate_name(data["name"])

    mobile = supplier.mobile
    if "mobile" in data:
        mobile = _validate_mobile(data["mobile"])

    email = supplier.email
    if "email" in data:
        email = _validate_email(data["email"])

    address = supplier.address
    if "address" in data:
        address = _validate_address(data["address"])

    opening_due = supplier.opening_due
    if "opening_due" in data:
        opening_due = _validate_decimal(data["opening_due"], "Opening due")

    is_active = supplier.is_active
    if "is_active" in data:
        is_active = _validate_is_active(data["is_active"])

    before = _snapshot(supplier)
    supplier.code = code
    supplier.name = name
    supplier.mobile = mobile  # type: ignore[assignment]
    supplier.email = email  # type: ignore[assignment]
    supplier.address = address  # type: ignore[assignment]
    supplier.opening_due = opening_due
    supplier.is_active = is_active

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Supplier code is already in use") from exc

    record_audit(
        db,
        actor_id=actor.id,
        entity_type="supplier",
        entity_id=supplier.id,
        action=(
            "STATUS"
            if is_active != before["is_active"]
            and code == before["code"]
            and name == before["name"]
            else "UPDATE"
        ),
        before=before,
        after=_snapshot(supplier),
        ip=ip,
    )
    db.commit()
    db.refresh(supplier)
    return supplier


def delete_supplier(
    db: Session, supplier: Supplier, actor: User, ip: str | None = None
) -> Supplier:
    if supplier.deleted_at is not None:
        return supplier
    before = _snapshot(supplier)
    supplier.is_active = False
    supplier.deleted_at = datetime.now(UTC)
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="supplier",
        entity_id=supplier.id,
        action="DELETE",
        before=before,
        after=_snapshot(supplier),
        ip=ip,
    )
    db.commit()
    db.refresh(supplier)
    return supplier


def activate_supplier(
    db: Session, supplier: Supplier, actor: User, ip: str | None = None
) -> Supplier:
    if supplier.is_active and supplier.deleted_at is None:
        return supplier
    before = _snapshot(supplier)
    supplier.is_active = True
    setattr(supplier, "deleted_at", None)
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="supplier",
        entity_id=supplier.id,
        action="STATUS",
        before=before,
        after=_snapshot(supplier),
        ip=ip,
    )
    db.commit()
    db.refresh(supplier)
    return supplier


def list_contacts(db: Session, supplier_id: int) -> list[PartyContact]:
    return party_repository.list_contacts(db, "SUPPLIER", supplier_id)


def create_contact(
    db: Session, supplier_id: int, data: dict[str, object], actor: User, ip: str | None = None
) -> PartyContact:
    name = _validate_name(data.get("name"))
    phone = _validate_mobile(data.get("phone"))
    email = _validate_email(data.get("email"))
    designation = data.get("designation")
    if designation is not None and not isinstance(designation, str):
        raise HTTPException(status_code=422, detail="Contact designation must be text")
    if isinstance(designation, str):
        designation = designation.strip() or None

    contact = PartyContact(
        party_type="SUPPLIER",
        party_id=supplier_id,
        name=name,
        phone=phone,
        email=email,
        designation=designation,
    )
    db.add(contact)
    db.flush()
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="supplier_contact",
        entity_id=contact.id,
        action="CREATE",
        after={
            "party_type": contact.party_type,
            "party_id": contact.party_id,
            "name": contact.name,
            "phone": contact.phone,
            "email": contact.email,
            "designation": contact.designation,
        },
        ip=ip,
    )
    db.commit()
    db.refresh(contact)
    return contact


def update_contact(
    db: Session,
    contact: PartyContact,
    data: dict[str, object],
    actor: User,
    ip: str | None = None,
) -> PartyContact:
    name = contact.name
    if "name" in data:
        name = _validate_name(data["name"])

    phone: str | None = contact.phone
    if "phone" in data:
        phone = _validate_mobile(data["phone"])

    email: str | None = contact.email
    if "email" in data:
        email = _validate_email(data["email"])

    designation: str | None = contact.designation
    if "designation" in data:
        value = data["designation"]
        if value is None:
            designation = None
        elif not isinstance(value, str):
            raise HTTPException(status_code=422, detail="Contact designation must be text")
        else:
            designation = value.strip() or None

    before = {
        "party_type": contact.party_type,
        "party_id": contact.party_id,
        "name": contact.name,
        "phone": contact.phone,
        "email": contact.email,
        "designation": contact.designation,
    }
    contact.name = name
    contact.phone = phone  # type: ignore[assignment]
    contact.email = email  # type: ignore[assignment]
    contact.designation = designation  # type: ignore[assignment]
    db.flush()
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="supplier_contact",
        entity_id=contact.id,
        action="UPDATE",
        before=before,
        after={
            "party_type": contact.party_type,
            "party_id": contact.party_id,
            "name": contact.name,
            "phone": contact.phone,
            "email": contact.email,
            "designation": contact.designation,
        },
        ip=ip,
    )
    db.commit()
    db.refresh(contact)
    return contact


def delete_contact(db: Session, contact: PartyContact, actor: User, ip: str | None = None) -> None:
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="supplier_contact",
        entity_id=contact.id,
        action="DELETE",
        before={
            "party_type": contact.party_type,
            "party_id": contact.party_id,
            "name": contact.name,
            "phone": contact.phone,
            "email": contact.email,
            "designation": contact.designation,
        },
        after=None,
        ip=ip,
    )
    db.delete(contact)
    db.commit()


def get_supplier_statement(db: Session, supplier: Supplier) -> dict[str, object]:
    balance = supplier.opening_due
    entries: list[dict[str, object]] = [
        {
            "date": supplier.created_at.isoformat(),
            "type": "OPENING_BALANCE",
            "description": "Opening balance",
            "amount": str(supplier.opening_due),
            "balance": str(balance),
        }
    ]
    from app.modules.direct_purchases import service as direct_purchase_service
    from app.modules.goods_receipts import service as goods_receipt_service

    purchase_entries = goods_receipt_service.list_supplier_due_entries(db, supplier.id)
    purchase_entries.extend(direct_purchase_service.list_supplier_due_entries(db, supplier.id))
    purchase_entries.sort(key=lambda entry: (str(entry["date"]), str(entry["description"])))
    for purchase in purchase_entries:
        amount = purchase["amount"]
        if not isinstance(amount, Decimal):
            raise TypeError("Goods receipt amount must be a Decimal")
        balance += amount
        entries.append(
            {
                "date": purchase["date"],
                "type": purchase["type"],
                "description": purchase["description"],
                "amount": str(amount),
                "balance": str(balance),
            }
        )
    return {
        "supplier_id": supplier.id,
        "supplier_name": supplier.name,
        "opening_due": str(supplier.opening_due),
        "entries": entries,
        "balance": str(balance),
    }


def _snapshot(supplier: Supplier) -> dict[str, object]:
    return {
        "code": supplier.code,
        "name": supplier.name,
        "mobile": supplier.mobile,
        "email": supplier.email,
        "address": supplier.address,
        "opening_due": str(supplier.opening_due),
        "is_active": supplier.is_active,
        "deleted_at": supplier.deleted_at.isoformat() if supplier.deleted_at else None,
    }
