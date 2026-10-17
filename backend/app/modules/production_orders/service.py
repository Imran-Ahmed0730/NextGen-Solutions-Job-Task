from datetime import UTC, datetime, time
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.boms import service as bom_service
from app.modules.boms.models import BOM
from app.modules.document_numbering.service import generate_next_number
from app.modules.inventory import service as inventory_service
from app.modules.inventory.models import MovementType
from app.modules.production_orders import repository
from app.modules.production_orders.models import (
    ProductionConsumption,
    ProductionOrder,
    ProductionOutput,
)
from app.modules.production_orders.schemas import (
    ProductionOrderBOMOption,
    ProductionOrderComplete,
    ProductionOrderCreate,
    ProductionOrderOptionsResponse,
    ProductionOrderWarehouseOption,
)
from app.modules.products import service as product_service
from app.modules.products.models import Product, ProductType
from app.modules.sales_orders import service as sales_order_service
from app.modules.warehouses import service as warehouse_service

DOCUMENT_TYPE = "PRODUCTION_ORDER"
QUANTITY_SCALE = Decimal("0.001")
CENT = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")
MAX_MONEY = Decimal("9999999999999999.99")


def list_production_orders(
    db: Session, *, offset: int = 0, limit: int = 50
) -> list[ProductionOrder]:
    return repository.list_production_orders(db, offset=offset, limit=limit)


def get_production_order(db: Session, production_order_id: int) -> ProductionOrder | None:
    return repository.get_production_order(db, production_order_id)


def get_production_order_options(db: Session) -> ProductionOrderOptionsResponse:
    boms = bom_service.list_boms(db, limit=200)
    warehouses = warehouse_service.list_warehouses(db, limit=200)
    return ProductionOrderOptionsResponse(
        boms=[
            ProductionOrderBOMOption(
                id=bom.id,
                code=bom.code,
                finished_product_id=bom.finished_product_id,
                output_qty=bom.output_qty,
                labor_cost_default=bom.labor_cost_default,
                overhead_cost_default=bom.overhead_cost_default,
            )
            for bom in boms
        ],
        warehouses=[
            ProductionOrderWarehouseOption(id=item.id, code=item.code, name=item.name)
            for item in warehouses
        ],
        sales_order_lines=sales_order_service.list_production_order_lines(db),
    )


def create_production_order(
    db: Session, payload: ProductionOrderCreate, actor: User, ip: str | None = None
) -> ProductionOrder:
    try:
        bom = _active_bom(db, payload.bom_id)
        _validate_finished_quantity(db, bom.finished_product_id, payload.planned_qty)
        warehouse = warehouse_service.get_active_warehouse(db, payload.warehouse_id)
        if warehouse is None:
            raise HTTPException(status_code=404, detail="Warehouse not found")
        _validate_sales_order_link(
            db,
            payload.sales_order_line_id,
            finished_product_id=bom.finished_product_id,
            warehouse_id=warehouse.id,
            for_update=True,
        )
        order = ProductionOrder(
            doc_no=generate_next_number(db, DOCUMENT_TYPE, payload.doc_date.year),
            doc_date=payload.doc_date,
            bom_id=bom.id,
            sales_order_line_id=payload.sales_order_line_id,
            finished_product_id=bom.finished_product_id,
            planned_qty=payload.planned_qty,
            warehouse_id=warehouse.id,
            status="DRAFT",
            created_by=actor.id,
        )
        db.add(order)
        db.flush()
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="production_order",
            entity_id=order.id,
            action="CREATE",
            after=_snapshot(order),
            ip=ip,
        )
        db.commit()
        return repository.get_production_order(db, order.id) or order
    except Exception:
        db.rollback()
        raise


def update_production_order(
    db: Session,
    production_order_id: int,
    payload: ProductionOrderCreate,
    actor: User,
    ip: str | None = None,
) -> ProductionOrder:
    try:
        order = repository.get_production_order(db, production_order_id, for_update=True)
        if order is None:
            raise HTTPException(status_code=404, detail="Production order not found")
        if order.status != "DRAFT":
            raise HTTPException(status_code=409, detail="PRODUCTION_ORDER_NOT_EDITABLE")
        if payload.doc_date.year != order.doc_date.year:
            raise HTTPException(
                status_code=422, detail="Document date year cannot change after numbering"
            )
        bom = _active_bom(db, payload.bom_id)
        _validate_finished_quantity(db, bom.finished_product_id, payload.planned_qty)
        warehouse = warehouse_service.get_active_warehouse(db, payload.warehouse_id)
        if warehouse is None:
            raise HTTPException(status_code=404, detail="Warehouse not found")
        _validate_sales_order_link(
            db,
            payload.sales_order_line_id,
            finished_product_id=bom.finished_product_id,
            warehouse_id=warehouse.id,
            for_update=True,
        )
        before = _snapshot(order)
        order.doc_date = payload.doc_date
        order.bom_id = bom.id
        # The installed SQLAlchemy/Python combination rejects nullable union mappings.
        setattr(order, "sales_order_line_id", payload.sales_order_line_id)
        order.finished_product_id = bom.finished_product_id
        order.planned_qty = payload.planned_qty
        order.warehouse_id = warehouse.id
        order.updated_at = datetime.now(UTC)
        db.flush()
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="production_order",
            entity_id=order.id,
            action="UPDATE",
            before=before,
            after=_snapshot(order),
            ip=ip,
        )
        db.commit()
        return repository.get_production_order(db, order.id) or order
    except Exception:
        db.rollback()
        raise


def start_production_order(
    db: Session,
    production_order_id: int,
    actor: User,
    ip: str | None = None,
) -> ProductionOrder:
    try:
        order = repository.get_production_order(db, production_order_id, for_update=True)
        if order is None:
            raise HTTPException(status_code=404, detail="Production order not found")
        if order.status != "DRAFT":
            raise HTTPException(status_code=409, detail="PRODUCTION_ORDER_CANNOT_START")
        bom = _active_bom(db, order.bom_id)
        _validate_sales_order_link(
            db,
            order.sales_order_line_id,
            finished_product_id=order.finished_product_id,
            warehouse_id=order.warehouse_id,
            for_update=True,
        )
        _check_material_availability(db, bom, order.planned_qty, order.warehouse_id)
        before = _snapshot(order)
        order.status = "IN_PROGRESS"
        order.updated_at = datetime.now(UTC)
        db.flush()
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="production_order",
            entity_id=order.id,
            action="STATUS",
            before=before,
            after=_snapshot(order),
            ip=ip,
        )
        db.commit()
        return repository.get_production_order(db, order.id) or order
    except Exception:
        db.rollback()
        raise


def cancel_production_order(
    db: Session,
    production_order_id: int,
    actor: User,
    ip: str | None = None,
) -> ProductionOrder:
    try:
        order = repository.get_production_order(db, production_order_id, for_update=True)
        if order is None:
            raise HTTPException(status_code=404, detail="Production order not found")
        if order.status not in {"DRAFT", "IN_PROGRESS"}:
            raise HTTPException(status_code=409, detail="PRODUCTION_ORDER_CANNOT_CANCEL")
        before = _snapshot(order)
        order.status = "CANCELLED"
        order.updated_at = datetime.now(UTC)
        db.flush()
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="production_order",
            entity_id=order.id,
            action="STATUS",
            before=before,
            after=_snapshot(order),
            ip=ip,
        )
        db.commit()
        return repository.get_production_order(db, order.id) or order
    except Exception:
        db.rollback()
        raise


def complete_production_order(
    db: Session,
    production_order_id: int,
    payload: ProductionOrderComplete,
    actor: User,
    ip: str | None = None,
) -> ProductionOrder:
    try:
        order = repository.get_production_order(db, production_order_id, for_update=True)
        if order is None:
            raise HTTPException(status_code=404, detail="Production order not found")
        if order.status != "IN_PROGRESS":
            raise HTTPException(status_code=409, detail="PRODUCTION_ORDER_NOT_IN_PROGRESS")
        bom = _active_bom(db, order.bom_id)
        _validate_sales_order_link(
            db,
            order.sales_order_line_id,
            finished_product_id=order.finished_product_id,
            warehouse_id=order.warehouse_id,
            for_update=True,
        )
        raw_ids = sorted({line.raw_product_id for line in bom.lines})
        expected_types = {product_id: ProductType.RAW for product_id in raw_ids}
        expected_types[order.finished_product_id] = ProductType.FINISHED
        locked_products = {
            product_id: _lock_active_product(
                db, product_id, expected_type=expected_types[product_id]
            )
            for product_id in sorted(expected_types)
        }
        finished_product = locked_products[order.finished_product_id]
        _validate_whole_qty(finished_product, payload.actual_qty)
        raw_products = {product_id: locked_products[product_id] for product_id in raw_ids}
        ingredient_quantities = _scaled_ingredients(bom, payload.actual_qty)
        consumption_rows: list[ProductionConsumption] = []
        material_cost = Decimal("0.00")
        for bom_line in bom.lines:
            qty = ingredient_quantities[bom_line.raw_product_id]
            product = raw_products[bom_line.raw_product_id]
            _validate_whole_qty(product, qty)
            unit_cost = product.avg_cost
            line_cost = (qty * unit_cost).quantize(CENT, rounding=ROUND_HALF_UP)
            material_cost += line_cost
            consumption_rows.append(
                ProductionConsumption(
                    product_id=product.id,
                    qty=qty,
                    unit_cost=unit_cost,
                    line_cost=line_cost,
                )
            )
        if material_cost > MAX_MONEY:
            raise HTTPException(status_code=422, detail="PRODUCTION_COST_EXCEEDS_LIMIT")
        total_cost = (material_cost + payload.labor_cost + payload.overhead_cost).quantize(
            CENT, rounding=ROUND_HALF_UP
        )
        if total_cost > MAX_MONEY:
            raise HTTPException(status_code=422, detail="PRODUCTION_COST_EXCEEDS_LIMIT")
        unit_cost = (total_cost / payload.actual_qty).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)

        old_finished_qty = inventory_service.get_product_total_on_hand(db, finished_product.id)
        next_average = inventory_service.weighted_average_cost(
            old_qty=old_finished_qty,
            old_avg_cost=finished_product.avg_cost,
            received_qty=payload.actual_qty,
            unit_cost=unit_cost,
        ).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)
        before = _snapshot(order)
        order.actual_qty = payload.actual_qty
        order.labor_cost = payload.labor_cost
        order.overhead_cost = payload.overhead_cost
        order.material_cost = material_cost
        order.total_cost = total_cost
        order.unit_cost = unit_cost
        order.status = "COMPLETED"
        order.updated_at = datetime.now(UTC)
        order.consumption = consumption_rows
        output = ProductionOutput(
            product_id=finished_product.id,
            qty=payload.actual_qty,
            unit_cost=unit_cost,
        )
        order.outputs = [output]
        db.flush()

        posted_at = datetime.combine(order.doc_date, time.min, tzinfo=UTC)
        for row in order.consumption:
            inventory_service.post_stock_movement(
                db,
                product_id=row.product_id,
                warehouse_id=order.warehouse_id,
                movement_type=MovementType.PRODUCTION_CONSUME,
                qty_signed=-row.qty,
                unit_cost=row.unit_cost,
                actor=actor,
                source_type=DOCUMENT_TYPE,
                source_id=order.id,
                source_line_id=row.id,
                txn_date=posted_at,
            )
        inventory_service.post_stock_movement(
            db,
            product_id=output.product_id,
            warehouse_id=order.warehouse_id,
            movement_type=MovementType.PRODUCTION_OUTPUT,
            qty_signed=output.qty,
            unit_cost=output.unit_cost,
            actor=actor,
            source_type=DOCUMENT_TYPE,
            source_id=order.id,
            source_line_id=output.id,
            txn_date=posted_at,
        )
        product_service.update_average_cost_for_production(
            db, product_id=finished_product.id, average_cost=next_average
        )
        if order.sales_order_line_id is not None:
            sales_order_service.record_production_output(
                db,
                sales_order_line_id=order.sales_order_line_id,
                qty=payload.actual_qty,
                actor=actor,
                ip=ip,
            )
        db.flush()
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="production_order",
            entity_id=order.id,
            action="POST",
            before=before,
            after=_snapshot(order),
            ip=ip,
        )
        db.commit()
        return repository.get_production_order(db, order.id) or order
    except Exception:
        db.rollback()
        raise


def _active_bom(db: Session, bom_id: int) -> BOM:
    bom = bom_service.get_bom(db, bom_id, active_only=True)
    if bom is None:
        raise HTTPException(status_code=404, detail="Active BOM not found")
    return bom


def _validate_sales_order_link(
    db: Session,
    sales_order_line_id: int | None,
    *,
    finished_product_id: int,
    warehouse_id: int,
    for_update: bool = False,
) -> None:
    if sales_order_line_id is None:
        return
    line_and_order = sales_order_service.get_production_order_line(
        db, sales_order_line_id, for_update=for_update
    )
    if line_and_order is None:
        raise HTTPException(status_code=404, detail="Sales order line not found")
    line, order = line_and_order
    if order.status != "DRAFT":
        raise HTTPException(status_code=409, detail="SALES_ORDER_NOT_PRODUCIBLE")
    if line.product_id != finished_product_id or order.warehouse_id != warehouse_id:
        raise HTTPException(status_code=422, detail="PRODUCTION_SALES_ORDER_LINE_MISMATCH")


def _lock_active_product(
    db: Session, product_id: int, *, expected_type: ProductType | None = None
) -> Product:
    product = product_service.lock_product_for_stock_posting(db, product_id)
    if (
        product is None
        or not product.is_active
        or product.deleted_at is not None
        or not product.is_stocked
        or (expected_type is not None and product.type != expected_type)
    ):
        raise HTTPException(status_code=409, detail="PRODUCTION_PRODUCT_NO_LONGER_AVAILABLE")
    return product


def _validate_finished_quantity(db: Session, product_id: int, qty: Decimal) -> None:
    product = _lock_active_product(db, product_id, expected_type=ProductType.FINISHED)
    _validate_whole_qty(product, qty)


def _validate_whole_qty(product: Product, qty: Decimal) -> None:
    if not product.unit.allow_decimal and qty != qty.to_integral_value():
        raise HTTPException(status_code=422, detail="Product unit does not allow decimal quantity")


def _scaled_ingredients(bom: BOM, output_qty: Decimal) -> dict[int, Decimal]:
    return {
        line.raw_product_id: (line.qty * output_qty / bom.output_qty).quantize(
            QUANTITY_SCALE, rounding=ROUND_HALF_UP
        )
        for line in bom.lines
    }


def _check_material_availability(
    db: Session, bom: BOM, output_qty: Decimal, warehouse_id: int
) -> None:
    quantities = _scaled_ingredients(bom, output_qty)
    raw_products = {
        product_id: _lock_active_product(db, product_id, expected_type=ProductType.RAW)
        for product_id in sorted(quantities)
    }
    pairs = {(product_id, warehouse_id) for product_id in quantities}
    available = inventory_service.get_available_quantities(db, pairs)
    for product_id, required_qty in quantities.items():
        _validate_whole_qty(raw_products[product_id], required_qty)
        if required_qty <= 0 or available[(product_id, warehouse_id)] < required_qty:
            raise HTTPException(status_code=409, detail="STOCK_INSUFFICIENT")


def _snapshot(order: ProductionOrder) -> dict[str, object]:
    return {
        "doc_no": order.doc_no,
        "doc_date": order.doc_date.isoformat(),
        "bom_id": order.bom_id,
        "sales_order_line_id": order.sales_order_line_id,
        "finished_product_id": order.finished_product_id,
        "planned_qty": str(order.planned_qty),
        "actual_qty": str(order.actual_qty) if order.actual_qty is not None else None,
        "warehouse_id": order.warehouse_id,
        "status": order.status,
        "labor_cost": str(order.labor_cost) if order.labor_cost is not None else None,
        "overhead_cost": (str(order.overhead_cost) if order.overhead_cost is not None else None),
        "material_cost": str(order.material_cost) if order.material_cost is not None else None,
        "total_cost": str(order.total_cost) if order.total_cost is not None else None,
        "unit_cost": str(order.unit_cost) if order.unit_cost is not None else None,
        "consumption": [
            {
                "product_id": line.product_id,
                "qty": str(line.qty),
                "unit_cost": str(line.unit_cost),
                "line_cost": str(line.line_cost),
            }
            for line in order.consumption
        ],
        "outputs": [
            {"product_id": line.product_id, "qty": str(line.qty), "unit_cost": str(line.unit_cost)}
            for line in order.outputs
        ],
    }
