from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.document_numbering.service import generate_next_number
from app.modules.products import service as product_service
from app.modules.products.models import Product
from app.modules.purchase_orders import repository
from app.modules.purchase_orders.models import PurchaseOrder, PurchaseOrderLine
from app.modules.purchase_orders.schemas import (
    PurchaseOrderCreate,
    PurchaseOrderOptionsResponse,
    PurchaseOrderProductOption,
    PurchaseOrderSupplierOption,
    PurchaseOrderUpdate,
    PurchaseOrderWarehouseOption,
)
from app.modules.suppliers import service as supplier_service
from app.modules.warehouses import service as warehouse_service

DOCUMENT_TYPE = "PURCHASE_ORDER"
CENT = Decimal("0.01")
MAX_MONEY = Decimal("9999999999999999.99")


def list_purchase_orders(db: Session, *, offset: int = 0, limit: int = 50) -> list[PurchaseOrder]:
    return repository.list_purchase_orders(db, offset=offset, limit=limit)


def get_purchase_order(db: Session, purchase_order_id: int) -> PurchaseOrder | None:
    return repository.get_purchase_order(db, purchase_order_id)


def get_purchase_order_options(db: Session) -> PurchaseOrderOptionsResponse:
    suppliers = supplier_service.list_suppliers(limit=200, db=db)
    warehouses = warehouse_service.list_warehouses(limit=200, db=db)
    products = product_service.list_products(limit=200, is_stocked=True, db=db)
    return PurchaseOrderOptionsResponse(
        suppliers=[
            PurchaseOrderSupplierOption(id=item.id, code=item.code, name=item.name)
            for item in suppliers
        ],
        warehouses=[
            PurchaseOrderWarehouseOption(id=item.id, code=item.code, name=item.name)
            for item in warehouses
        ],
        products=[
            PurchaseOrderProductOption(
                id=item.id,
                sku=item.sku,
                name=item.name,
                unit_code=item.unit.code,
                allow_decimal=item.unit.allow_decimal,
            )
            for item in products
        ],
    )


def create_purchase_order(
    db: Session,
    payload: PurchaseOrderCreate,
    actor: User,
    ip: str | None = None,
) -> PurchaseOrder:
    try:
        supplier = supplier_service.get_supplier(db, payload.supplier_id)
        if supplier is None or not supplier.is_active or supplier.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Supplier not found")
        if warehouse_service.get_active_warehouse(db, payload.warehouse_id) is None:
            raise HTTPException(status_code=404, detail="Warehouse not found")
        _validate_lines(db, payload)
        lines, subtotal, discount, total = _build_lines(payload)
        purchase_order = PurchaseOrder(
            doc_no=generate_next_number(db, DOCUMENT_TYPE, payload.doc_date.year),
            doc_date=payload.doc_date,
            supplier_id=supplier.id,
            warehouse_id=payload.warehouse_id,
            status="DRAFT",
            expected_date=payload.expected_date,
            subtotal=subtotal,
            discount=discount,
            total=total,
            note=payload.note,
            created_by=actor.id,
            lines=lines,
        )
        db.add(purchase_order)
        db.flush()
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="purchase_order",
            entity_id=purchase_order.id,
            action="CREATE",
            after=_snapshot(purchase_order),
            ip=ip,
        )
        db.commit()
        return repository.get_purchase_order(db, purchase_order.id) or purchase_order
    except Exception:
        db.rollback()
        raise


def update_purchase_order(
    db: Session,
    purchase_order_id: int,
    payload: PurchaseOrderUpdate,
    actor: User,
    ip: str | None = None,
) -> PurchaseOrder:
    try:
        purchase_order = repository.get_purchase_order(db, purchase_order_id, for_update=True)
        if purchase_order is None:
            raise HTTPException(status_code=404, detail="Purchase order not found")
        if purchase_order.status != "DRAFT":
            raise HTTPException(status_code=409, detail="PURCHASE_ORDER_NOT_EDITABLE")
        if payload.doc_date.year != purchase_order.doc_date.year:
            raise HTTPException(
                status_code=422, detail="Document date year cannot change after numbering"
            )
        supplier = supplier_service.get_supplier(db, payload.supplier_id)
        if supplier is None or not supplier.is_active or supplier.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Supplier not found")
        if warehouse_service.get_active_warehouse(db, payload.warehouse_id) is None:
            raise HTTPException(status_code=404, detail="Warehouse not found")
        _validate_lines(db, payload)
        lines, subtotal, discount, total = _build_lines(payload)

        before = _snapshot(purchase_order)
        purchase_order.doc_date = payload.doc_date
        purchase_order.supplier_id = supplier.id
        purchase_order.warehouse_id = payload.warehouse_id
        purchase_order.expected_date = payload.expected_date
        purchase_order.subtotal = subtotal
        purchase_order.discount = discount
        purchase_order.total = total
        purchase_order.note = payload.note
        purchase_order.lines = lines
        purchase_order.updated_at = datetime.now(UTC)
        db.flush()
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="purchase_order",
            entity_id=purchase_order.id,
            action="UPDATE",
            before=before,
            after=_snapshot(purchase_order),
            ip=ip,
        )
        db.commit()
        return repository.get_purchase_order(db, purchase_order.id) or purchase_order
    except Exception:
        db.rollback()
        raise


def submit_purchase_order(
    db: Session,
    purchase_order_id: int,
    actor: User,
    ip: str | None = None,
) -> PurchaseOrder:
    try:
        purchase_order = repository.get_purchase_order(db, purchase_order_id, for_update=True)
        if purchase_order is None:
            raise HTTPException(status_code=404, detail="Purchase order not found")
        if purchase_order.status != "DRAFT":
            raise HTTPException(status_code=409, detail="Only draft purchase orders can be submitted")
        before = _snapshot(purchase_order)
        purchase_order.status = "PENDING_APPROVAL"
        purchase_order.updated_at = datetime.now(UTC)
        db.flush()
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="purchase_order",
            entity_id=purchase_order.id,
            action="SUBMIT",
            before=before,
            after=_snapshot(purchase_order),
            ip=ip,
        )
        db.commit()
        return repository.get_purchase_order(db, purchase_order.id) or purchase_order
    except Exception:
        db.rollback()
        raise


def approve_purchase_order(
    db: Session,
    purchase_order_id: int,
    actor: User,
    ip: str | None = None,
) -> PurchaseOrder:
    try:
        purchase_order = repository.get_purchase_order(db, purchase_order_id, for_update=True)
        if purchase_order is None:
            raise HTTPException(status_code=404, detail="Purchase order not found")
        if purchase_order.status not in ("DRAFT", "PENDING_APPROVAL"):
            raise HTTPException(
                status_code=409, detail="Only draft or pending purchase orders can be approved"
            )
        before = _snapshot(purchase_order)
        purchase_order.status = "APPROVED"
        purchase_order.updated_at = datetime.now(UTC)
        db.flush()
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="purchase_order",
            entity_id=purchase_order.id,
            action="APPROVE",
            before=before,
            after=_snapshot(purchase_order),
            ip=ip,
        )
        db.commit()
        return repository.get_purchase_order(db, purchase_order.id) or purchase_order
    except Exception:
        db.rollback()
        raise


def cancel_purchase_order(
    db: Session,
    purchase_order_id: int,
    actor: User,
    ip: str | None = None,
) -> PurchaseOrder:
    try:
        purchase_order = repository.get_purchase_order(db, purchase_order_id, for_update=True)
        if purchase_order is None:
            raise HTTPException(status_code=404, detail="Purchase order not found")
        if purchase_order.status in ("CLOSED", "CANCELLED"):
            raise HTTPException(status_code=409, detail="Purchase order is already closed or cancelled")
        if any(line.received_qty > 0 for line in purchase_order.lines):
            raise HTTPException(
                status_code=409, detail="Cannot cancel a purchase order with received goods"
            )
        before = _snapshot(purchase_order)
        purchase_order.status = "CANCELLED"
        purchase_order.updated_at = datetime.now(UTC)
        db.flush()
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="purchase_order",
            entity_id=purchase_order.id,
            action="CANCEL",
            before=before,
            after=_snapshot(purchase_order),
            ip=ip,
        )
        db.commit()
        return repository.get_purchase_order(db, purchase_order.id) or purchase_order
    except Exception:
        db.rollback()
        raise


def _validate_lines(db: Session, payload: PurchaseOrderCreate | PurchaseOrderUpdate) -> None:
    products: dict[int, Product] = {}
    for product_id in sorted({line.product_id for line in payload.lines}):
        product = product_service.lock_product_for_stock_posting(db, product_id)
        if product is None or not product.is_active or product.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Product not found")
        if not product.is_stocked:
            raise HTTPException(status_code=422, detail="Only stocked products can be ordered")
        products[product_id] = product

    for line in payload.lines:
        if not line.qty.is_finite() or line.qty <= 0:
            raise HTTPException(status_code=422, detail="Order quantity must be positive")
        if not line.unit_price.is_finite() or line.unit_price < 0:
            raise HTTPException(status_code=422, detail="Unit price cannot be negative")
        product = products[line.product_id]
        if not product.unit.allow_decimal and line.qty != line.qty.to_integral_value():
            raise HTTPException(
                status_code=422, detail="Product unit does not allow decimal quantity"
            )


def _build_lines(
    payload: PurchaseOrderCreate | PurchaseOrderUpdate,
) -> tuple[list[PurchaseOrderLine], Decimal, Decimal, Decimal]:
    lines = [
        PurchaseOrderLine(
            product_id=line.product_id,
            qty=line.qty,
            unit_price=line.unit_price,
            line_total=(line.qty * line.unit_price).quantize(CENT, rounding=ROUND_HALF_UP),
            received_qty=Decimal("0.000"),
        )
        for line in payload.lines
    ]
    subtotal = sum((line.line_total for line in lines), start=Decimal("0.00"))
    if subtotal > MAX_MONEY:
        raise HTTPException(status_code=422, detail="Purchase order total exceeds supported amount")
    discount = payload.discount
    if not discount.is_finite() or discount < 0:
        raise HTTPException(status_code=422, detail="Discount cannot be negative")
    if discount > MAX_MONEY:
        raise HTTPException(status_code=422, detail="Discount exceeds supported amount")
    if discount > subtotal:
        raise HTTPException(status_code=422, detail="Discount cannot exceed the subtotal")
    total = subtotal - discount
    return lines, subtotal, discount, total


def _snapshot(purchase_order: PurchaseOrder) -> dict[str, object]:
    return {
        "doc_no": purchase_order.doc_no,
        "doc_date": purchase_order.doc_date.isoformat(),
        "supplier_id": purchase_order.supplier_id,
        "warehouse_id": purchase_order.warehouse_id,
        "status": purchase_order.status,
        "expected_date": (
            purchase_order.expected_date.isoformat() if purchase_order.expected_date else None
        ),
        "subtotal": str(purchase_order.subtotal),
        "discount": str(purchase_order.discount),
        "total": str(purchase_order.total),
        "note": purchase_order.note,
        "lines": [
            {
                "id": line.id,
                "product_id": line.product_id,
                "qty": str(line.qty),
                "unit_price": str(line.unit_price),
                "line_total": str(line.line_total),
                "received_qty": str(line.received_qty),
            }
            for line in purchase_order.lines
        ],
    }
