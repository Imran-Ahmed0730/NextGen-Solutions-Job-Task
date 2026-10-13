from datetime import UTC, date, datetime

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.price_lists import repository
from app.modules.price_lists.models import PriceList, ProductPrice
from app.modules.products.models import Product


def list_price_lists(
    db: Session, *, include_inactive: bool = False, offset: int = 0, limit: int = 50
) -> list[PriceList]:
    return repository.list_price_lists(
        db, include_inactive=include_inactive, offset=offset, limit=limit
    )


def get_price_list(db: Session, price_list_id: int) -> PriceList | None:
    return repository.get_price_list(db, price_list_id)


def _validate_name(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=422, detail="Price list name is required")
    name = value.strip()
    if len(name) > 100:
        raise HTTPException(status_code=422, detail="Price list name is too long")
    return name


def _validate_is_default(value: object) -> bool:
    if not isinstance(value, bool):
        raise HTTPException(status_code=422, detail="is_default must be a boolean")
    return value


def _validate_is_active(value: object) -> bool:
    if not isinstance(value, bool):
        raise HTTPException(status_code=422, detail="is_active must be a boolean")
    return value


def _validate_dates(valid_from: date | None, valid_to: date | None) -> None:
    if valid_from is not None and valid_to is not None and valid_to < valid_from:
        raise HTTPException(
            status_code=422, detail="valid_to must be on or after valid_from"
        )


def _clear_other_defaults(db: Session, *, exclude_id: int | None = None) -> None:
    for other in repository.list_default_price_lists(db, exclude_id=exclude_id):
        other.is_default = False


def create_price_list(
    db: Session, data: dict[str, object], actor: User, ip: str | None = None
) -> PriceList:
    name = _validate_name(data.get("name"))
    is_default = _validate_is_default(data.get("is_default", False))
    is_active = _validate_is_active(data.get("is_active", True))

    valid_from = data.get("valid_from")
    valid_to = data.get("valid_to")
    if valid_from is not None and not isinstance(valid_from, date):
        raise HTTPException(status_code=422, detail="valid_from must be a date")
    if valid_to is not None and not isinstance(valid_to, date):
        raise HTTPException(status_code=422, detail="valid_to must be a date")
    _validate_dates(valid_from, valid_to)

    price_list = PriceList(
        name=name,
        is_default=is_default,
        valid_from=valid_from,
        valid_to=valid_to,
        is_active=is_active,
    )
    if is_default:
        _clear_other_defaults(db)
    db.add(price_list)
    db.flush()

    record_audit(
        db,
        actor_id=actor.id,
        entity_type="price_list",
        entity_id=price_list.id,
        action="CREATE",
        after=_snapshot(price_list),
        ip=ip,
    )
    db.commit()
    db.refresh(price_list)
    return price_list


def update_price_list(
    db: Session,
    price_list: PriceList,
    data: dict[str, object],
    actor: User,
    ip: str | None = None,
) -> PriceList:
    if price_list.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Price list not found")

    name = price_list.name
    if "name" in data:
        name = _validate_name(data["name"])

    is_default = price_list.is_default
    if "is_default" in data:
        is_default = _validate_is_default(data["is_default"])

    is_active = price_list.is_active
    if "is_active" in data:
        is_active = _validate_is_active(data["is_active"])

    valid_from = price_list.valid_from
    if "valid_from" in data:
        value = data["valid_from"]
        if value is not None and not isinstance(value, date):
            raise HTTPException(status_code=422, detail="valid_from must be a date")
        valid_from = value

    valid_to = price_list.valid_to
    if "valid_to" in data:
        value = data["valid_to"]
        if value is not None and not isinstance(value, date):
            raise HTTPException(status_code=422, detail="valid_to must be a date")
        valid_to = value

    _validate_dates(valid_from, valid_to)

    before = _snapshot(price_list)
    price_list.name = name
    price_list.is_default = is_default
    price_list.is_active = is_active
    price_list.valid_from = valid_from
    price_list.valid_to = valid_to

    if is_default:
        _clear_other_defaults(db, exclude_id=price_list.id)

    db.flush()
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="price_list",
        entity_id=price_list.id,
        action=(
            "STATUS"
            if is_active != before["is_active"]
            and name == before["name"]
            and is_default == before["is_default"]
            and valid_from == before["valid_from"]
            and valid_to == before["valid_to"]
            else "UPDATE"
        ),
        before=before,
        after=_snapshot(price_list),
        ip=ip,
    )
    db.commit()
    db.refresh(price_list)
    return price_list


def delete_price_list(
    db: Session, price_list: PriceList, actor: User, ip: str | None = None
) -> PriceList:
    if price_list.deleted_at is not None:
        return price_list
    before = _snapshot(price_list)
    price_list.is_active = False
    price_list.is_default = False
    price_list.deleted_at = datetime.now(UTC)
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="price_list",
        entity_id=price_list.id,
        action="DELETE",
        before=before,
        after=_snapshot(price_list),
        ip=ip,
    )
    db.commit()
    db.refresh(price_list)
    return price_list


def activate_price_list(
    db: Session, price_list: PriceList, actor: User, ip: str | None = None
) -> PriceList:
    if price_list.is_active and price_list.deleted_at is None:
        return price_list
    before = _snapshot(price_list)
    price_list.is_active = True
    setattr(price_list, "deleted_at", None)
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="price_list",
        entity_id=price_list.id,
        action="STATUS",
        before=before,
        after=_snapshot(price_list),
        ip=ip,
    )
    db.commit()
    db.refresh(price_list)
    return price_list


def _snapshot(price_list: PriceList) -> dict[str, object]:
    return {
        "name": price_list.name,
        "is_default": price_list.is_default,
        "valid_from": price_list.valid_from.isoformat() if price_list.valid_from else None,
        "valid_to": price_list.valid_to.isoformat() if price_list.valid_to else None,
        "is_active": price_list.is_active,
        "deleted_at": price_list.deleted_at.isoformat() if price_list.deleted_at else None,
    }


def list_product_prices(db: Session, price_list_id: int) -> list[ProductPrice]:
    price_list = repository.get_price_list(db, price_list_id)
    if price_list is None or price_list.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Price list not found")
    return repository.list_product_prices(db, price_list_id)


def create_product_price(
    db: Session,
    price_list_id: int,
    data: dict[str, object],
    actor: User,
    ip: str | None = None,
) -> ProductPrice:
    price_list = repository.get_price_list(db, price_list_id)
    if price_list is None or price_list.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Price list not found")

    product_id = data.get("product_id")
    if not isinstance(product_id, int) or product_id <= 0:
        raise HTTPException(status_code=422, detail="Product id must be a positive integer")
    product = db.get(Product, product_id)
    if product is None or product.deleted_at is not None:
        raise HTTPException(status_code=400, detail="Product does not exist")

    if "price" not in data:
        raise HTTPException(status_code=422, detail="Price is required")
    try:
        price = data["price"]
        if isinstance(price, bool):
            raise ValueError
        from decimal import Decimal

        price_value = Decimal(str(price))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail="Price is not a valid number") from exc
    if price_value < 0:
        raise HTTPException(status_code=422, detail="Price must be zero or greater")

    if repository.get_product_price_by_list_and_product(db, price_list_id, product_id) is not None:
        raise HTTPException(status_code=409, detail="Price already exists for this product")

    product_price = ProductPrice(
        price_list_id=price_list_id,
        product_id=product_id,
        price=price_value,
    )
    db.add(product_price)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Price already exists for this product"
        ) from exc

    record_audit(
        db,
        actor_id=actor.id,
        entity_type="product_price",
        entity_id=product_price.id,
        action="CREATE",
        after=_product_price_snapshot(product_price),
        ip=ip,
    )
    db.commit()
    db.refresh(product_price)
    return product_price


def get_product_price(db: Session, product_price_id: int) -> ProductPrice | None:
    return repository.get_product_price(db, product_price_id)


def update_product_price(
    db: Session,
    product_price: ProductPrice,
    data: dict[str, object],
    actor: User,
    ip: str | None = None,
) -> ProductPrice:
    # ensure price list exists
    price_list = repository.get_price_list(db, product_price.price_list_id)
    if price_list is None or price_list.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Price list not found")

    product_id = product_price.product_id
    if "product_id" in data:
        value = data["product_id"]
        if not isinstance(value, int) or value <= 0:
            raise HTTPException(status_code=422, detail="Product id must be a positive integer")
        product = db.get(Product, value)
        if product is None or product.deleted_at is not None:
            raise HTTPException(status_code=400, detail="Product does not exist")
        product_id = value
        if product_id != product_price.product_id:
            existing = repository.get_product_price_by_list_and_product(
                db, product_price.price_list_id, product_id
            )
            if existing is not None and existing.id != product_price.id:
                raise HTTPException(status_code=409, detail="Price already exists for this product")

    price = product_price.price
    if "price" in data:
        try:
            value = data["price"]
            if isinstance(value, bool):
                raise ValueError
            from decimal import Decimal

            price = Decimal(str(value))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=422, detail="Price is not a valid number") from exc
        if price < 0:
            raise HTTPException(status_code=422, detail="Price must be zero or greater")

    before = _product_price_snapshot(product_price)
    product_price.product_id = product_id
    product_price.price = price
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Price already exists for this product"
        ) from exc

    record_audit(
        db,
        actor_id=actor.id,
        entity_type="product_price",
        entity_id=product_price.id,
        action="UPDATE",
        before=before,
        after=_product_price_snapshot(product_price),
        ip=ip,
    )
    db.commit()
    db.refresh(product_price)
    return product_price


def delete_product_price(
    db: Session, product_price: ProductPrice, actor: User, ip: str | None = None
) -> None:
    price_list = repository.get_price_list(db, product_price.price_list_id)
    if price_list is None or price_list.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Price list not found")

    before = _product_price_snapshot(product_price)
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="product_price",
        entity_id=product_price.id,
        action="DELETE",
        before=before,
        after=None,
        ip=ip,
    )
    db.delete(product_price)
    db.commit()


def _product_price_snapshot(product_price: ProductPrice) -> dict[str, object]:
    return {
        "price_list_id": product_price.price_list_id,
        "product_id": product_price.product_id,
        "price": str(product_price.price),
    }