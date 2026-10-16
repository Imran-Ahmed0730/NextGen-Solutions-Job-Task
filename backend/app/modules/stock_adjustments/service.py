from datetime import UTC, datetime, time
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.approvals.service import request_approval_if_required
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
            status="DRAFT",
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

        approval_amount = sum(
            (
                abs(line.qty_signed) * products[line.product_id].avg_cost
                for line in adjustment.lines
            ),
            start=Decimal("0"),
        )
        approval_request = request_approval_if_required(
            db,
            doc_type=DOCUMENT_TYPE,
            doc_id=adjustment.id,
            amount=approval_amount,
            actor=actor,
            ip=ip,
        )
        if approval_request:
            adjustment.status = "PENDING_APPROVAL"
        else:
            adjustment.status = "POSTED"
            _post_adjustment_effects(db, adjustment, actor, ip)

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


def decide_adjustment(
    db: Session,
    adjustment_id: int,
    *,
    approved: bool,
    actor: User,
    ip: str | None = None,
) -> StockAdjustment:
    adjustment = repository.get_adjustment_for_update(db, adjustment_id)
    if adjustment is None:
        raise HTTPException(status_code=404, detail="Stock adjustment not found")
    if adjustment.status != "PENDING_APPROVAL":
        raise HTTPException(status_code=409, detail="Stock adjustment is not awaiting approval")
    before = _snapshot(adjustment)
    if approved:
        products: dict[int, Product] = {}
        for product_id in sorted(line.product_id for line in adjustment.lines):
            product = product_service.lock_product_for_stock_posting(db, product_id)
            if product is None or not product.is_active or product.deleted_at is not None:
                raise HTTPException(
                    status_code=409, detail="An adjusted product is no longer active"
                )
            if not product.is_stocked:
                raise HTTPException(
                    status_code=409, detail="An adjusted product is no longer stocked"
                )
            products[product_id] = product
        adjustment.status = "POSTED"
        _post_adjustment_effects(db, adjustment, actor, ip)
    else:
        adjustment.status = "DRAFT"
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="stock_adjustment",
        entity_id=adjustment.id,
        action="STATUS",
        before=before,
        after=_snapshot(adjustment),
        ip=ip,
    )
    db.flush()
    return adjustment


def update_rejected_adjustment(
    db: Session,
    adjustment_id: int,
    payload: StockAdjustmentCreate,
    actor: User,
    ip: str | None = None,
) -> StockAdjustment:
    try:
        adjustment = repository.get_adjustment_for_update(db, adjustment_id)
        if adjustment is None:
            raise HTTPException(status_code=404, detail="Stock adjustment not found")
        if adjustment.status != "DRAFT":
            raise HTTPException(
                status_code=409, detail="Only rejected stock adjustments can be edited"
            )
        if payload.doc_date.year != adjustment.doc_date.year:
            raise HTTPException(
                status_code=422, detail="Document date year cannot change after numbering"
            )
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

        before = _snapshot(adjustment)
        adjustment.doc_date = payload.doc_date
        adjustment.warehouse_id = payload.warehouse_id
        adjustment.reason = payload.reason
        adjustment.lines = [
            StockAdjustmentLine(
                product_id=line.product_id,
                qty_signed=line.qty_signed,
                unit_cost=products[line.product_id].avg_cost,
            )
            for line in payload.lines
        ]
        amount = sum(
            (
                abs(line.qty_signed) * products[line.product_id].avg_cost
                for line in adjustment.lines
            ),
            start=Decimal("0"),
        )
        approval_request = request_approval_if_required(
            db,
            doc_type=DOCUMENT_TYPE,
            doc_id=adjustment.id,
            amount=amount,
            actor=actor,
            ip=ip,
        )
        if approval_request:
            adjustment.status = "PENDING_APPROVAL"
        else:
            adjustment.status = "POSTED"
            _post_adjustment_effects(db, adjustment, actor, ip)
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="stock_adjustment",
            entity_id=adjustment.id,
            action="UPDATE",
            before=before,
            after=_snapshot(adjustment),
            ip=ip,
        )
        db.commit()
        db.refresh(adjustment)
        return adjustment
    except Exception:
        db.rollback()
        raise


def _post_adjustment_effects(
    db: Session,
    adjustment: StockAdjustment,
    actor: User,
    ip: str | None,
) -> None:
    posted_at = datetime.combine(adjustment.doc_date, time.min, tzinfo=UTC)
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
