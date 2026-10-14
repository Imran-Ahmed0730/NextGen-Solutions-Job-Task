from datetime import UTC, datetime, time
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.document_numbering.service import generate_next_number
from app.modules.inventory import repository as inventory_repository
from app.modules.inventory.models import MovementType
from app.modules.inventory.service import post_stock_movement
from app.modules.physical_counts import repository
from app.modules.physical_counts.models import PhysicalCount, PhysicalCountLine
from app.modules.physical_counts.schemas import (
    PhysicalCountCreate,
    PhysicalCountLinesUpdate,
    PhysicalCountListItem,
    PhysicalCountWarehouseOption,
)
from app.modules.products import service as product_service
from app.modules.products.models import Product
from app.modules.warehouses import service as warehouse_service

DOCUMENT_TYPE = "PHYSICAL_COUNT"


def list_counts(db: Session, *, offset: int = 0, limit: int = 50) -> list[PhysicalCountListItem]:
    return [
        PhysicalCountListItem(
            id=physical_count.id,
            doc_no=physical_count.doc_no,
            count_date=physical_count.count_date,
            warehouse_id=physical_count.warehouse_id,
            status=physical_count.status,
            total_lines=total_lines,
            counted_lines=counted_lines,
        )
        for physical_count, total_lines, counted_lines in repository.list_counts(
            db, offset=offset, limit=limit
        )
    ]


def get_count(db: Session, count_id: int) -> PhysicalCount | None:
    return repository.get_count(db, count_id)


def get_count_options(db: Session) -> list[PhysicalCountWarehouseOption]:
    warehouses = warehouse_service.list_warehouses(db, limit=200)
    return [
        PhysicalCountWarehouseOption(id=warehouse.id, code=warehouse.code, name=warehouse.name)
        for warehouse in warehouses
    ]


def start_count(
    db: Session,
    payload: PhysicalCountCreate,
    actor: User,
    ip: str | None = None,
) -> PhysicalCount:
    try:
        if warehouse_service.get_active_warehouse(db, payload.warehouse_id) is None:
            raise HTTPException(status_code=404, detail="Warehouse not found")
        product_ids = repository.list_product_ids_for_count(db)
        if not product_ids:
            raise HTTPException(status_code=422, detail="No active stocked products to count")

        lines: list[PhysicalCountLine] = []
        for product_id in product_ids:
            product = product_service.lock_product_for_stock_posting(db, product_id)
            if product is None or not product.is_active or product.deleted_at is not None:
                raise HTTPException(status_code=409, detail="PHYSICAL_COUNT_SCOPE_CHANGED")
            if not product.is_stocked:
                raise HTTPException(status_code=409, detail="PHYSICAL_COUNT_SCOPE_CHANGED")
            balance = inventory_repository.get_balance(
                db, product_id, payload.warehouse_id, for_update=True
            )
            lines.append(
                PhysicalCountLine(
                    product_id=product_id,
                    system_qty=balance.qty_on_hand if balance is not None else Decimal("0.000"),
                )
            )

        physical_count = PhysicalCount(
            count_date=payload.count_date,
            warehouse_id=payload.warehouse_id,
            status="OPEN",
            created_by=actor.id,
            lines=lines,
        )
        db.add(physical_count)
        db.flush()
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="physical_count",
            entity_id=physical_count.id,
            action="CREATE",
            after=_snapshot(physical_count),
            ip=ip,
        )
        db.commit()
        return repository.get_count(db, physical_count.id) or physical_count
    except Exception:
        db.rollback()
        raise


def update_counted_quantities(
    db: Session,
    count_id: int,
    payload: PhysicalCountLinesUpdate,
    actor: User,
    ip: str | None = None,
) -> PhysicalCount:
    try:
        physical_count = repository.get_count(db, count_id, for_update=True)
        if physical_count is None:
            raise HTTPException(status_code=404, detail="Physical count not found")
        if physical_count.status == "POSTED":
            raise HTTPException(status_code=409, detail="DOCUMENT_POSTED")
        product_ids = [line.product_id for line in payload.lines]
        if len(product_ids) != len(set(product_ids)):
            raise HTTPException(
                status_code=422, detail="A product may appear only once in a count update"
            )
        count_lines = {line.product_id: line for line in physical_count.lines}
        if any(product_id not in count_lines for product_id in product_ids):
            raise HTTPException(
                status_code=422, detail="Product is not included in this physical count"
            )

        products: dict[int, Product] = {}
        for product_id in sorted(product_ids):
            product = product_service.lock_product_for_stock_posting(db, product_id)
            if product is None:
                raise HTTPException(status_code=409, detail="PHYSICAL_COUNT_SCOPE_CHANGED")
            products[product_id] = product

        before = _snapshot(physical_count)
        for payload_line in payload.lines:
            if payload_line.counted_qty < 0:
                raise HTTPException(status_code=422, detail="Counted quantity cannot be negative")
            product = products[payload_line.product_id]
            if not product.unit.allow_decimal and (
                payload_line.counted_qty != payload_line.counted_qty.to_integral_value()
            ):
                raise HTTPException(
                    status_code=422, detail="Product unit does not allow decimal quantity"
                )
            count_line = count_lines[payload_line.product_id]
            count_line.counted_qty = payload_line.counted_qty
            count_line.variance_qty = payload_line.counted_qty - count_line.system_qty

        physical_count.status = (
            "COUNTED"
            if all(line.counted_qty is not None for line in physical_count.lines)
            else "OPEN"
        )
        physical_count.updated_at = datetime.now(UTC)
        db.flush()
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="physical_count",
            entity_id=physical_count.id,
            action="UPDATE",
            before=before,
            after=_snapshot(physical_count),
            ip=ip,
        )
        db.commit()
        return repository.get_count(db, physical_count.id) or physical_count
    except Exception:
        db.rollback()
        raise


def post_count(
    db: Session,
    count_id: int,
    actor: User,
    ip: str | None = None,
) -> PhysicalCount:
    try:
        physical_count = repository.get_count(db, count_id, for_update=True)
        if physical_count is None:
            raise HTTPException(status_code=404, detail="Physical count not found")
        if physical_count.status == "POSTED":
            raise HTTPException(status_code=409, detail="DOCUMENT_POSTED")
        if not physical_count.lines or any(
            line.counted_qty is None for line in physical_count.lines
        ):
            raise HTTPException(status_code=409, detail="PHYSICAL_COUNT_INCOMPLETE")

        current_product_ids = repository.list_product_ids_for_count(db)
        count_lines = {line.product_id: line for line in physical_count.lines}
        if set(current_product_ids) != set(count_lines):
            raise HTTPException(status_code=409, detail="PHYSICAL_COUNT_SCOPE_CHANGED")

        products: dict[int, Product] = {}
        for product_id in sorted(current_product_ids):
            product = product_service.lock_product_for_stock_posting(db, product_id)
            if product is None or not product.is_active or product.deleted_at is not None:
                raise HTTPException(status_code=409, detail="PHYSICAL_COUNT_SCOPE_CHANGED")
            if not product.is_stocked:
                raise HTTPException(status_code=409, detail="PHYSICAL_COUNT_SCOPE_CHANGED")
            products[product_id] = product

        for product_id in sorted(current_product_ids):
            line = count_lines[product_id]
            balance = inventory_repository.get_balance(
                db, product_id, physical_count.warehouse_id, for_update=True
            )
            current_qty = balance.qty_on_hand if balance is not None else Decimal("0.000")
            if current_qty != line.system_qty:
                raise HTTPException(status_code=409, detail="PHYSICAL_COUNT_STALE_STOCK")

        now = datetime.now(UTC)
        posted_at = datetime.combine(physical_count.count_date, time.min, tzinfo=UTC)
        before = _snapshot(physical_count)
        physical_count.doc_no = generate_next_number(
            db, DOCUMENT_TYPE, physical_count.count_date.year
        )
        physical_count.status = "POSTED"
        physical_count.posted_by = actor.id
        physical_count.posted_at = now
        physical_count.updated_at = now

        for product_id in sorted(current_product_ids):
            line = count_lines[product_id]
            if line.counted_qty is None:
                raise HTTPException(status_code=409, detail="PHYSICAL_COUNT_INCOMPLETE")
            variance = line.counted_qty - line.system_qty
            line.variance_qty = variance
            if variance == 0:
                continue
            post_stock_movement(
                db,
                product_id=product_id,
                warehouse_id=physical_count.warehouse_id,
                movement_type=MovementType.COUNT_ADJUSTMENT,
                qty_signed=variance,
                unit_cost=products[product_id].avg_cost,
                actor=actor,
                source_type=DOCUMENT_TYPE,
                source_id=physical_count.id,
                source_line_id=line.id,
                txn_date=posted_at,
            )

        record_audit(
            db,
            actor_id=actor.id,
            entity_type="physical_count",
            entity_id=physical_count.id,
            action="UPDATE",
            before=before,
            after=_snapshot(physical_count),
            ip=ip,
        )
        db.commit()
        return repository.get_count(db, physical_count.id) or physical_count
    except Exception:
        db.rollback()
        raise


def _snapshot(physical_count: PhysicalCount) -> dict[str, object]:
    return {
        "doc_no": physical_count.doc_no,
        "count_date": physical_count.count_date.isoformat(),
        "warehouse_id": physical_count.warehouse_id,
        "status": physical_count.status,
        "created_by": physical_count.created_by,
        "posted_by": physical_count.posted_by,
        "posted_at": physical_count.posted_at.isoformat()
        if physical_count.posted_at is not None
        else None,
        "lines": [
            {
                "id": line.id,
                "product_id": line.product_id,
                "system_qty": str(line.system_qty),
                "counted_qty": str(line.counted_qty) if line.counted_qty is not None else None,
                "variance_qty": str(line.variance_qty) if line.variance_qty is not None else None,
            }
            for line in physical_count.lines
        ],
    }
