from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.product_categories.models import ProductCategory
from app.modules.products import repository
from app.modules.products.models import Product, ProductType
from app.modules.units.models import Unit


def list_products(
    db: Session,
    *,
    search: str | None = None,
    category_id: int | None = None,
    product_type: ProductType | None = None,
    is_stocked: bool | None = None,
    include_inactive: bool = False,
    offset: int = 0,
    limit: int = 50,
) -> list[Product]:
    return repository.list_products(
        db,
        search=search,
        category_id=category_id,
        product_type=product_type,
        is_stocked=is_stocked,
        include_inactive=include_inactive,
        offset=offset,
        limit=limit,
    )


def count_stocked_products(db: Session, *, search: str | None = None) -> int:
    return repository.count_stocked_products(db, search=search)


def get_product(db: Session, product_id: int) -> Product | None:
    return repository.get_product(db, product_id)


def lock_product_for_stock_posting(db: Session, product_id: int) -> Product | None:
    return repository.lock_product_for_stock_posting(db, product_id)


def update_average_cost_for_production(
    db: Session, *, product_id: int, average_cost: Decimal
) -> Product:
    if not average_cost.is_finite() or average_cost < 0:
        raise HTTPException(status_code=422, detail="Average cost must be nonnegative")
    if average_cost != average_cost.quantize(Decimal("0.0001")):
        raise HTTPException(status_code=422, detail="Average cost supports at most 4 decimals")
    product = repository.lock_product_for_stock_posting(db, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    product.avg_cost = average_cost
    db.flush()
    return product


def create_product(
    db: Session, data: dict[str, object], actor: User, ip: str | None = None
) -> Product:
    sku = str(data["sku"]).strip()
    name = str(data["name"]).strip()
    if not sku:
        raise HTTPException(status_code=422, detail="Product SKU is required")
    if not name:
        raise HTTPException(status_code=422, detail="Product name is required")

    _ensure_sku_available(db, sku)

    category_id = int(str(data["category_id"]))
    unit_id = int(str(data["unit_id"]))
    _ensure_category_valid(db, category_id)
    _ensure_unit_valid(db, unit_id)

    raw_type = data["type"]
    product_type = raw_type if isinstance(raw_type, ProductType) else ProductType(str(raw_type))

    reorder_level = (
        Decimal(str(data["reorder_level"]))
        if "reorder_level" in data and data["reorder_level"] is not None
        else Decimal("0.000")
    )
    sales_price_default = (
        Decimal(str(data["sales_price_default"]))
        if "sales_price_default" in data and data["sales_price_default"] is not None
        else Decimal("0.00")
    )
    is_stocked = bool(data.get("is_stocked", True))
    is_active = bool(data.get("is_active", True))
    description = (
        str(data["description"]).strip()
        if "description" in data and data["description"] is not None
        else None
    )

    product = Product(
        sku=sku,
        name=name,
        type=product_type,
        category_id=category_id,
        unit_id=unit_id,
        is_stocked=is_stocked,
        reorder_level=reorder_level,
        avg_cost=Decimal("0.0000"),
        sales_price_default=sales_price_default,
        description=description,
        is_active=is_active,
    )
    db.add(product)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise _duplicate_sku_error() from exc

    record_audit(
        db,
        actor_id=actor.id,
        entity_type="product",
        entity_id=product.id,
        action="CREATE",
        after=_snapshot(product),
        ip=ip,
    )
    db.commit()
    db.refresh(product)
    return product


def update_product(
    db: Session,
    product: Product,
    data: dict[str, object],
    actor: User,
    ip: str | None = None,
) -> Product:
    if product.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Product not found")

    sku = product.sku
    if "sku" in data and data["sku"] is not None:
        sku = str(data["sku"]).strip()
        if not sku:
            raise HTTPException(status_code=422, detail="Product SKU is required")
        _ensure_sku_available(db, sku, exclude_id=product.id)

    name = product.name
    if "name" in data and data["name"] is not None:
        name = str(data["name"]).strip()
        if not name:
            raise HTTPException(status_code=422, detail="Product name is required")

    category_id = product.category_id
    if "category_id" in data and data["category_id"] is not None:
        category_id = int(str(data["category_id"]))
        _ensure_category_valid(db, category_id)

    unit_id = product.unit_id
    if "unit_id" in data and data["unit_id"] is not None:
        unit_id = int(str(data["unit_id"]))
        _ensure_unit_valid(db, unit_id)

    product_type = product.type
    if "type" in data and data["type"] is not None:
        raw_type = data["type"]
        product_type = raw_type if isinstance(raw_type, ProductType) else ProductType(str(raw_type))

    reorder_level = product.reorder_level
    if "reorder_level" in data and data["reorder_level"] is not None:
        reorder_level = Decimal(str(data["reorder_level"]))

    sales_price_default = product.sales_price_default
    if "sales_price_default" in data and data["sales_price_default"] is not None:
        sales_price_default = Decimal(str(data["sales_price_default"]))

    is_stocked = product.is_stocked
    if "is_stocked" in data and data["is_stocked"] is not None:
        is_stocked = bool(data["is_stocked"])

    is_active = product.is_active
    if "is_active" in data and data["is_active"] is not None:
        is_active = bool(data["is_active"])

    description = product.description
    if "description" in data:
        description = str(data["description"]).strip() if data["description"] is not None else None

    before = _snapshot(product)
    product.sku = sku
    product.name = name
    product.type = product_type
    product.category_id = category_id
    product.unit_id = unit_id
    product.is_stocked = is_stocked
    product.reorder_level = reorder_level
    product.sales_price_default = sales_price_default
    product.description = description
    product.is_active = is_active

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise _duplicate_sku_error() from exc

    record_audit(
        db,
        actor_id=actor.id,
        entity_type="product",
        entity_id=product.id,
        action="UPDATE",
        before=before,
        after=_snapshot(product),
        ip=ip,
    )
    db.commit()
    db.refresh(product)
    return product


def delete_product(db: Session, product: Product, actor: User, ip: str | None = None) -> Product:
    if product.deleted_at is not None:
        return product
    before = _snapshot(product)
    product.is_active = False
    product.deleted_at = datetime.now(UTC)
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="product",
        entity_id=product.id,
        action="DELETE",
        before=before,
        after=_snapshot(product),
        ip=ip,
    )
    db.commit()
    db.refresh(product)
    return product


def activate_product(db: Session, product: Product, actor: User, ip: str | None = None) -> Product:
    if product.is_active and product.deleted_at is None:
        return product
    before = _snapshot(product)
    product.is_active = True
    setattr(product, "deleted_at", None)
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="product",
        entity_id=product.id,
        action="STATUS",
        before=before,
        after=_snapshot(product),
        ip=ip,
    )
    db.commit()
    db.refresh(product)
    return product


def _ensure_sku_available(db: Session, sku: str, *, exclude_id: int | None = None) -> None:
    if repository.get_product_by_sku(db, sku, exclude_id=exclude_id) is not None:
        raise _duplicate_sku_error()


def _ensure_category_valid(db: Session, category_id: int) -> ProductCategory:
    category = db.get(ProductCategory, category_id)
    if category is None or category.deleted_at is not None or not category.is_active:
        raise HTTPException(
            status_code=400, detail="Product category does not exist or is inactive"
        )
    return category


def _ensure_unit_valid(db: Session, unit_id: int) -> Unit:
    unit = db.get(Unit, unit_id)
    if unit is None or unit.deleted_at is not None or not unit.is_active:
        raise HTTPException(status_code=400, detail="Unit does not exist or is inactive")
    return unit


def _duplicate_sku_error() -> HTTPException:
    return HTTPException(status_code=409, detail="Product SKU is already in use")


def _snapshot(product: Product) -> dict[str, object]:
    return {
        "sku": product.sku,
        "name": product.name,
        "type": product.type.value if hasattr(product.type, "value") else str(product.type),
        "category_id": product.category_id,
        "unit_id": product.unit_id,
        "is_stocked": product.is_stocked,
        "reorder_level": str(product.reorder_level),
        "avg_cost": str(product.avg_cost),
        "sales_price_default": str(product.sales_price_default),
        "description": product.description,
        "is_active": product.is_active,
        "deleted_at": product.deleted_at.isoformat() if product.deleted_at else None,
    }
