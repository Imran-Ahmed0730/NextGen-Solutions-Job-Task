from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.customers import service as customer_service
from app.modules.document_numbering.service import generate_next_number
from app.modules.inventory import service as inventory_service
from app.modules.inventory.models import StockReservation
from app.modules.products import service as product_service
from app.modules.products.models import Product
from app.modules.sales.models import SalesOrder, SalesOrderLine
from app.modules.sales_orders import repository
from app.modules.sales_orders.schemas import (
    SalesOrderCreate,
    SalesOrderCustomerOption,
    SalesOrderOptionsResponse,
    SalesOrderProductOption,
    SalesOrderUpdate,
    SalesOrderWarehouseOption,
)
from app.modules.warehouses import service as warehouse_service

DOCUMENT_TYPE = "SALES_ORDER"
CENT = Decimal("0.01")
MAX_MONEY = Decimal("9999999999999999.99")


def list_sales_orders(db: Session, *, offset: int = 0, limit: int = 50) -> list[SalesOrder]:
    return repository.list_sales_orders(db, offset=offset, limit=limit)


def get_sales_order(db: Session, sales_order_id: int) -> SalesOrder | None:
    return repository.get_sales_order(db, sales_order_id)


def reserve_order_line(
    db: Session,
    *,
    sales_order_id: int,
    line_id: int,
    qty: Decimal,
    actor: User,
    ip: str | None = None,
) -> SalesOrder:
    try:
        line = db.get(SalesOrderLine, line_id)
        if line is None or line.order_id != sales_order_id:
            raise HTTPException(status_code=404, detail="Sales order line not found")
        inventory_service.reserve_stock(
            db,
            sales_order_line_id=line.id,
            qty=qty,
            actor=actor,
            ip=ip,
        )
        db.flush()
        order = repository.get_sales_order(db, sales_order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="Sales order not found")
        db.commit()
        return order
    except Exception:
        db.rollback()
        raise


def release_order_reservation(
    db: Session,
    *,
    sales_order_id: int,
    reservation_id: int,
    actor: User,
    ip: str | None = None,
) -> SalesOrder:
    try:
        reservation = db.get(StockReservation, reservation_id)
        if reservation is None:
            raise HTTPException(status_code=404, detail="Stock reservation not found")
        line = db.get(SalesOrderLine, reservation.sales_order_line_id)
        if line is None or line.order_id != sales_order_id:
            raise HTTPException(status_code=404, detail="Stock reservation not found")
        qty_remaining = reservation.qty - reservation.qty_consumed - reservation.qty_released
        if qty_remaining <= 0:
            raise HTTPException(status_code=409, detail="RESERVATION_QUANTITY_EXCEEDED")
        inventory_service.release_reservation(
            db,
            reservation_id=reservation.id,
            qty=qty_remaining,
            actor=actor,
            ip=ip,
        )
        db.flush()
        order = repository.get_sales_order(db, sales_order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="Sales order not found")
        db.commit()
        return order
    except Exception:
        db.rollback()
        raise


def get_sales_order_options(db: Session) -> SalesOrderOptionsResponse:
    customers = customer_service.list_customers(db, limit=200)
    warehouses = warehouse_service.list_warehouses(db, limit=200)
    products = product_service.list_products(db, limit=200)
    return SalesOrderOptionsResponse(
        customers=[
            SalesOrderCustomerOption(id=item.id, code=item.code, name=item.name)
            for item in customers
        ],
        warehouses=[
            SalesOrderWarehouseOption(id=item.id, code=item.code, name=item.name)
            for item in warehouses
        ],
        products=[
            SalesOrderProductOption(
                id=item.id,
                sku=item.sku,
                name=item.name,
                unit_code=item.unit.code,
                allow_decimal=item.unit.allow_decimal,
            )
            for item in products
        ],
    )


def create_sales_order(
    db: Session,
    payload: SalesOrderCreate,
    actor: User,
    ip: str | None = None,
) -> SalesOrder:
    try:
        customer = customer_service.get_customer(db, payload.customer_id)
        if customer is None or not customer.is_active or customer.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Customer not found")
        warehouse = warehouse_service.get_active_warehouse(db, payload.warehouse_id)
        if warehouse is None:
            raise HTTPException(status_code=404, detail="Warehouse not found")
        _validate_products(db, payload)
        lines, subtotal, discount, total = _build_lines(payload)
        order = SalesOrder(
            doc_no=generate_next_number(db, DOCUMENT_TYPE, payload.doc_date.year),
            doc_date=payload.doc_date,
            customer_id=customer.id,
            warehouse_id=warehouse.id,
            status="DRAFT",
            delivery_date=payload.delivery_date,
            subtotal=subtotal,
            discount=discount,
            total=total,
            note=payload.note,
            created_by=actor.id,
            lines=lines,
        )
        db.add(order)
        db.flush()
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="sales_order",
            entity_id=order.id,
            action="CREATE",
            after=_snapshot(order),
            ip=ip,
        )
        db.commit()
        return repository.get_sales_order(db, order.id) or order
    except Exception:
        db.rollback()
        raise


def update_sales_order(
    db: Session,
    sales_order_id: int,
    payload: SalesOrderUpdate,
    actor: User,
    ip: str | None = None,
) -> SalesOrder:
    try:
        order = repository.get_sales_order(db, sales_order_id, for_update=True)
        if order is None:
            raise HTTPException(status_code=404, detail="Sales order not found")
        if order.status != "DRAFT":
            raise HTTPException(status_code=409, detail="SALES_ORDER_NOT_EDITABLE")
        if any(line.reservations for line in order.lines):
            raise HTTPException(status_code=409, detail="SALES_ORDER_HAS_RESERVATION_HISTORY")
        if payload.doc_date.year != order.doc_date.year:
            raise HTTPException(
                status_code=422, detail="Document date year cannot change after numbering"
            )
        customer = customer_service.get_customer(db, payload.customer_id)
        if customer is None or not customer.is_active or customer.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Customer not found")
        warehouse = warehouse_service.get_active_warehouse(db, payload.warehouse_id)
        if warehouse is None:
            raise HTTPException(status_code=404, detail="Warehouse not found")
        _validate_products(db, payload)
        lines, subtotal, discount, total = _build_lines(payload)

        before = _snapshot(order)
        order.doc_date = payload.doc_date
        order.customer_id = customer.id
        order.warehouse_id = warehouse.id
        order.delivery_date = payload.delivery_date
        order.subtotal = subtotal
        order.discount = discount
        order.total = total
        order.note = payload.note
        order.lines = lines
        order.updated_at = datetime.now(UTC)
        db.flush()
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="sales_order",
            entity_id=order.id,
            action="UPDATE",
            before=before,
            after=_snapshot(order),
            ip=ip,
        )
        db.commit()
        return repository.get_sales_order(db, order.id) or order
    except Exception:
        db.rollback()
        raise


def _validate_products(db: Session, payload: SalesOrderCreate | SalesOrderUpdate) -> None:
    products: dict[int, Product] = {}
    for product_id in {line.product_id for line in payload.lines}:
        product = product_service.get_product(db, product_id)
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found")
        if not product.is_active or product.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Product not found")
        products[product_id] = product

    for line in payload.lines:
        product = products[line.product_id]
        if (
            not product.unit.allow_decimal
            and line.qty_ordered != line.qty_ordered.to_integral_value()
        ):
            raise HTTPException(
                status_code=422, detail="Product unit does not allow decimal quantity"
            )


def _build_lines(
    payload: SalesOrderCreate | SalesOrderUpdate,
) -> tuple[list[SalesOrderLine], Decimal, Decimal, Decimal]:
    lines: list[SalesOrderLine] = []
    subtotal = Decimal("0.00")
    for line in payload.lines:
        raw_line_total = line.qty_ordered * line.unit_price
        if raw_line_total > MAX_MONEY:
            raise HTTPException(
                status_code=422, detail="Sales order total exceeds supported amount"
            )
        line_total = raw_line_total.quantize(CENT, rounding=ROUND_HALF_UP)
        subtotal += line_total
        lines.append(
            SalesOrderLine(
                product_id=line.product_id,
                qty_ordered=line.qty_ordered,
                unit_price=line.unit_price,
                line_total=line_total,
            )
        )
    if subtotal > MAX_MONEY:
        raise HTTPException(status_code=422, detail="Sales order total exceeds supported amount")
    if payload.discount > subtotal:
        raise HTTPException(status_code=422, detail="Discount cannot exceed the subtotal")
    return lines, subtotal, payload.discount, subtotal - payload.discount


def _snapshot(order: SalesOrder) -> dict[str, object]:
    return {
        "doc_no": order.doc_no,
        "doc_date": order.doc_date.isoformat(),
        "customer_id": order.customer_id,
        "warehouse_id": order.warehouse_id,
        "status": order.status,
        "delivery_date": order.delivery_date.isoformat() if order.delivery_date else None,
        "subtotal": str(order.subtotal),
        "discount": str(order.discount),
        "total": str(order.total),
        "note": order.note,
        "lines": [
            {
                "product_id": line.product_id,
                "qty_ordered": str(line.qty_ordered),
                "unit_price": str(line.unit_price),
                "line_total": str(line.line_total),
                "qty_reserved": str(line.qty_reserved),
                "qty_produced": str(line.qty_produced),
                "qty_delivered": str(line.qty_delivered),
            }
            for line in order.lines
        ],
    }
