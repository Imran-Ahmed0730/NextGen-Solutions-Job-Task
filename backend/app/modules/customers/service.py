from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.customers import repository
from app.modules.customers.models import Customer
from app.modules.parties import repository as party_repository
from app.modules.parties.models import PartyContact
from app.modules.price_lists.models import PriceList


def list_customers(
    db: Session,
    *,
    include_inactive: bool = False,
    offset: int = 0,
    limit: int = 50,
    search: str | None = None,
) -> list[Customer]:
    return repository.list_customers(
        db, include_inactive=include_inactive, offset=offset, limit=limit, search=search
    )


def get_customer(db: Session, customer_id: int) -> Customer | None:
    return repository.get_customer(db, customer_id)


def _validate_code(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=422, detail="Customer code is required")
    code = value.strip()
    if len(code) > 30:
        raise HTTPException(status_code=422, detail="Customer code is too long")
    return code


def _validate_name(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=422, detail="Customer name is required")
    name = value.strip()
    if len(name) > 255:
        raise HTTPException(status_code=422, detail="Customer name is too long")
    return name


def _validate_mobile(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise HTTPException(status_code=422, detail="Customer mobile must be text")
    mobile = value.strip()
    if not mobile:
        return None
    if len(mobile) > 30:
        raise HTTPException(status_code=422, detail="Customer mobile is too long")
    return mobile


def _validate_email(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise HTTPException(status_code=422, detail="Customer email must be text")
    email = value.strip()
    if not email:
        return None
    if len(email) > 255:
        raise HTTPException(status_code=422, detail="Customer email is too long")
    return email


def _validate_address(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise HTTPException(status_code=422, detail="Customer address must be text")
    address = value.strip()
    if not address:
        return None
    return address


def _validate_decimal(value: object, field_name: str, *, allow_negative: bool = False) -> Decimal:
    if value is None:
        return Decimal("0.00")
    if isinstance(value, bool):
        raise HTTPException(status_code=422, detail=f"{field_name} must be a number")
    try:
        number = Decimal(str(value))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"{field_name} must be a number") from exc
    if not allow_negative and number < 0:
        raise HTTPException(status_code=422, detail=f"{field_name} cannot be negative")
    return number


def _validate_is_active(value: object) -> bool:
    if not isinstance(value, bool):
        raise HTTPException(status_code=422, detail="is_active must be a boolean")
    return value


def _ensure_code_available(db: Session, code: str, *, exclude_id: int | None = None) -> None:
    existing = repository.get_customer_by_code(db, code)
    if existing is not None and existing.id != exclude_id:
        raise HTTPException(status_code=409, detail="Customer code is already in use")


def _validate_price_list(db: Session, value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise HTTPException(status_code=422, detail="Price list id must be a positive integer")
    price_list = db.get(PriceList, value)
    if price_list is None or price_list.deleted_at is not None:
        raise HTTPException(status_code=400, detail="Price list does not exist")
    return value


def create_customer(
    db: Session, data: dict[str, object], actor: User, ip: str | None = None
) -> Customer:
    code = _validate_code(data.get("code"))
    name = _validate_name(data.get("name"))
    mobile = _validate_mobile(data.get("mobile"))
    email = _validate_email(data.get("email"))
    address = _validate_address(data.get("address"))
    credit_limit = _validate_decimal(data.get("credit_limit", Decimal("0.00")), "Credit limit")
    opening_due = _validate_decimal(data.get("opening_due", Decimal("0.00")), "Opening due")
    price_list_id = _validate_price_list(db, data.get("price_list_id"))
    is_active = _validate_is_active(data.get("is_active", True))

    _ensure_code_available(db, code)

    customer = Customer(
        code=code,
        name=name,
        mobile=mobile,
        email=email,
        address=address,
        credit_limit=credit_limit,
        opening_due=opening_due,
        price_list_id=price_list_id,
        is_active=is_active,
    )
    db.add(customer)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Customer code is already in use") from exc

    record_audit(
        db,
        actor_id=actor.id,
        entity_type="customer",
        entity_id=customer.id,
        action="CREATE",
        after=_snapshot(customer),
        ip=ip,
    )
    db.commit()
    db.refresh(customer)
    return customer


def update_customer(
    db: Session,
    customer: Customer,
    data: dict[str, object],
    actor: User,
    ip: str | None = None,
) -> Customer:
    if customer.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Customer not found")

    code = customer.code
    if "code" in data:
        code = _validate_code(data["code"])
        if code != customer.code:
            _ensure_code_available(db, code, exclude_id=customer.id)

    name = customer.name
    if "name" in data:
        name = _validate_name(data["name"])

    mobile = customer.mobile
    if "mobile" in data:
        mobile = _validate_mobile(data["mobile"])

    email = customer.email
    if "email" in data:
        email = _validate_email(data["email"])

    address = customer.address
    if "address" in data:
        address = _validate_address(data["address"])

    credit_limit = customer.credit_limit
    if "credit_limit" in data:
        credit_limit = _validate_decimal(data["credit_limit"], "Credit limit")

    opening_due = customer.opening_due
    if "opening_due" in data:
        opening_due = _validate_decimal(data["opening_due"], "Opening due", allow_negative=True)

    price_list_id = customer.price_list_id
    if "price_list_id" in data:
        price_list_id = _validate_price_list(db, data["price_list_id"])

    is_active = customer.is_active
    if "is_active" in data:
        is_active = _validate_is_active(data["is_active"])

    before = _snapshot(customer)
    customer.code = code
    customer.name = name
    customer.mobile = mobile  # type: ignore[assignment]
    customer.email = email  # type: ignore[assignment]
    customer.address = address  # type: ignore[assignment]
    customer.credit_limit = credit_limit
    customer.opening_due = opening_due
    customer.price_list_id = price_list_id
    customer.is_active = is_active

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Customer code is already in use") from exc

    record_audit(
        db,
        actor_id=actor.id,
        entity_type="customer",
        entity_id=customer.id,
        action=(
            "STATUS"
            if is_active != before["is_active"]
            and code == before["code"]
            and name == before["name"]
            else "UPDATE"
        ),
        before=before,
        after=_snapshot(customer),
        ip=ip,
    )
    db.commit()
    db.refresh(customer)
    return customer


def delete_customer(
    db: Session, customer: Customer, actor: User, ip: str | None = None
) -> Customer:
    if customer.deleted_at is not None:
        return customer
    before = _snapshot(customer)
    customer.is_active = False
    customer.deleted_at = datetime.now(UTC)
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="customer",
        entity_id=customer.id,
        action="DELETE",
        before=before,
        after=_snapshot(customer),
        ip=ip,
    )
    db.commit()
    db.refresh(customer)
    return customer


def activate_customer(
    db: Session, customer: Customer, actor: User, ip: str | None = None
) -> Customer:
    if customer.is_active and customer.deleted_at is None:
        return customer
    before = _snapshot(customer)
    customer.is_active = True
    setattr(customer, "deleted_at", None)
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="customer",
        entity_id=customer.id,
        action="STATUS",
        before=before,
        after=_snapshot(customer),
        ip=ip,
    )
    db.commit()
    db.refresh(customer)
    return customer


def list_contacts(db: Session, customer_id: int) -> list[PartyContact]:
    return party_repository.list_contacts(db, "CUSTOMER", customer_id)


def create_contact(
    db: Session, customer_id: int, data: dict[str, object], actor: User, ip: str | None = None
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
        party_type="CUSTOMER",
        party_id=customer_id,
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
        entity_type="customer_contact",
        entity_id=contact.id,
        action="CREATE",
        after=_contact_snapshot(contact),
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

    before = _contact_snapshot(contact)
    contact.name = name
    contact.phone = phone  # type: ignore[assignment]
    contact.email = email  # type: ignore[assignment]
    contact.designation = designation  # type: ignore[assignment]
    db.flush()
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="customer_contact",
        entity_id=contact.id,
        action="UPDATE",
        before=before,
        after=_contact_snapshot(contact),
        ip=ip,
    )
    db.commit()
    db.refresh(contact)
    return contact


def delete_contact(
    db: Session, contact: PartyContact, actor: User, ip: str | None = None
) -> None:
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="customer_contact",
        entity_id=contact.id,
        action="DELETE",
        before=_contact_snapshot(contact),
        after=None,
        ip=ip,
    )
    db.delete(contact)
    db.commit()


def get_customer_statement(db: Session, customer: Customer) -> dict[str, object]:
    balance = Decimal("0.00")
    entries: list[dict[str, object]] = [
        {
            "date": customer.created_at.isoformat(),
            "type": "OPENING_BALANCE",
            "description": "Opening balance",
            "amount": customer.opening_due,
        }
    ]
    from app.modules.money_collections import repository as collection_repository
    from app.modules.money_collections.service import due_entry_data

    entries.extend(
        due_entry_data(collection)
        for collection in collection_repository.list_customer_collections(db, customer.id)
    )
    opening_entry, *due_entries = entries
    due_entries.sort(key=lambda entry: (str(entry["date"]), str(entry["description"])))
    entries = [opening_entry, *due_entries]
    statement_entries: list[dict[str, str]] = []
    for entry in entries:
        amount = entry["amount"]
        if not isinstance(amount, Decimal):
            raise TypeError("Customer statement amount must be a Decimal")
        balance += amount
        statement_entries.append(
            {
                "date": str(entry["date"]),
                "type": str(entry["type"]),
                "description": str(entry["description"]),
                "amount": str(amount),
                "balance": str(balance),
            }
        )
    return {
        "customer_id": customer.id,
        "customer_name": customer.name,
        "opening_due": str(customer.opening_due),
        "entries": statement_entries,
        "balance": str(balance),
    }


def _snapshot(customer: Customer) -> dict[str, object]:
    return {
        "code": customer.code,
        "name": customer.name,
        "mobile": customer.mobile,
        "email": customer.email,
        "address": customer.address,
        "credit_limit": str(customer.credit_limit),
        "opening_due": str(customer.opening_due),
        "price_list_id": customer.price_list_id,
        "is_active": customer.is_active,
        "deleted_at": customer.deleted_at.isoformat() if customer.deleted_at else None,
    }


def _contact_snapshot(contact: PartyContact) -> dict[str, object]:
    return {
        "party_type": contact.party_type,
        "party_id": contact.party_id,
        "name": contact.name,
        "phone": contact.phone,
        "email": contact.email,
        "designation": contact.designation,
    }