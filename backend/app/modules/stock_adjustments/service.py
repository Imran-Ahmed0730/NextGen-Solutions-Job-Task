from datetime import UTC, datetime, time
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.document_numbering.service import generate_next_number
from app.modules.inventory.models import MovementType
from app.modules.inventory.service import post_stock_movement
from app.modules.products import service as product_service
from app.modules.products.models import Product
from app.modules.stock_adjustments import repository
from app.modules.stock_adjustments.models import StockAdjustment, StockAdjustmentLine
from app.modules.stock_adjustments.schemas import (
    AdjustmentProductOption,
    AdjustmentWarehouseOption,
    StockAdjustmentCreate,
    StockAdjustmentOptionsResponse,
)
from app.modules.warehouses import service as warehouse_service

DOCUMENT_TYPE = "STOCK_ADJUSTMENT"


def list_adjustments(db: Session, *, offset: int = 0, limit: int = 50) -> list[StockAdjustment]:
    return repository.list_adjustments(db, offset=offset, limit=limit)


def get_adjustment(db: Session, adjustment_id: int) -> StockAdjustment | None:
    return repository.get_adjustment(db, adjustment_id)


def get_adjustment_options(db: Session) -> StockAdjustmentOptionsResponse:
    warehouses = warehouse_service.list_warehouses(db, limit=200)
    products = product_service.list_products(db, is_stocked=True, limit=200)
    return StockAdjustmentOptionsResponse(
        warehouses=[
            AdjustmentWarehouseOption(id=item.id, code=item.code, name=item.name)
            for item in warehouses
        ],
        products=[
            AdjustmentProductOption(
                id=item.id,
                sku=item.sku,
                name=item.name,
                unit_code=item.unit.code,
                is_stocked=item.is_stocked,
            )
            for item in products
        ],
    )


def post_adjustment(
    db: Session,
    payload: StockAdjustmentCreate,
    actor: User,
    ip: str | None = None,
) -> StockAdjustment:
    try:
        if warehouse_service.get_active_warehouse(db, payload.warehouse_id) is None:
            raise HTTPException(status_code=404, detail="Warehouse not found")
        product_ids = [line.product_id for line in payload.lines]
        if len(product_ids) != len(set(product_ids)):
            raise HTTPException(
                status_code=422, detail="A product may appear only once in an adjustment"
            )
        if any(line.qty_signed == 0 for line in payload.lines):
            raise HTTPException(status_code=422, detail="Adjustment quantities cannot be zero")

        products: dict[int, Product] = {}
        for product_id in sorted(product_ids):
            product = product_service.lock_product_for_stock_posting(db, product_id)
            if product is None or not product.is_active or product.deleted_at is not None:
                raise HTTPException(status_code=404, detail="Product not found")
            if not product.is_stocked:
                raise HTTPException(status_code=422, detail="Only stocked products can be adjusted")
            products[product_id] = product

        adjustment = StockAdjustment(
            doc_no=generate_next_number(db, DOCUMENT_TYPE, payload.doc_date.year),
            doc_date=payload.doc_date,
            warehouse_id=payload.warehouse_id,
            reason=payload.reason,
            status="POSTED",
            lines=[
                StockAdjustmentLine(
                    product_id=line.product_id,
                    qty_signed=line.qty_signed,
                    unit_cost=products[line.product_id].avg_cost,
                )
                for line in payload.lines
            ],
        )
        db.add(adjustment)
        db.flush()

        posted_at = datetime.combine(payload.doc_date, time.min, tzinfo=UTC)
        for adjustment_line in sorted(adjustment.lines, key=lambda item: item.product_id):
            movement_type = (
                MovementType.ADJUSTMENT_IN
                if adjustment_line.qty_signed > Decimal("0")
                else MovementType.ADJUSTMENT_OUT
            )
            post_stock_movement(
                db,
                product_id=adjustment_line.product_id,
                warehouse_id=adjustment.warehouse_id,
                movement_type=movement_type,
                qty_signed=adjustment_line.qty_signed,
                unit_cost=adjustment_line.unit_cost,
                actor=actor,
                source_type=DOCUMENT_TYPE,
                source_id=adjustment.id,
                source_line_id=adjustment_line.id,
                note=adjustment.reason,
                txn_date=posted_at,
            )

        record_audit(
            db,
            actor_id=actor.id,
            entity_type="stock_adjustment",
            entity_id=adjustment.id,
            action="CREATE",
            after=_snapshot(adjustment),
            ip=ip,
        )
        db.commit()
        db.refresh(adjustment)
        return adjustment
    except Exception:
        db.rollback()
        raise


def _snapshot(adjustment: StockAdjustment) -> dict[str, object]:
    return {
        "doc_no": adjustment.doc_no,
        "doc_date": adjustment.doc_date.isoformat(),
        "warehouse_id": adjustment.warehouse_id,
        "reason": adjustment.reason,
        "status": adjustment.status,
        "lines": [
            {
                "id": line.id,
                "product_id": line.product_id,
                "qty_signed": str(line.qty_signed),
                "unit_cost": str(line.unit_cost),
            }
            for line in adjustment.lines
        ],
    }
