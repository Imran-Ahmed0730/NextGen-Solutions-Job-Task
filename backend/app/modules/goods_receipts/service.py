from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.company_settings import service as company_settings_service
from app.modules.document_numbering.service import generate_next_number
from app.modules.goods_receipts import repository
from app.modules.goods_receipts.models import GoodsReceipt, GoodsReceiptLine
from app.modules.goods_receipts.schemas import (
    GoodsReceiptCreate,
    GoodsReceiptOptionsResponse,
    GoodsReceiptOrderLineOption,
    GoodsReceiptOrderOption,
)
from app.modules.inventory.models import MovementType
from app.modules.inventory.service import (
    get_product_total_on_hand,
    post_stock_movement,
    weighted_average_cost,
)
from app.modules.products import service as product_service
from app.modules.purchase_orders.models import PurchaseOrder
from app.modules.suppliers import service as supplier_service
from app.modules.warehouses import service as warehouse_service

DOCUMENT_TYPE = "GOODS_RECEIPT"
CENT = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")
MAX_MONEY = Decimal("9999999999999999.99")
RECEIVABLE_PO_STATUSES = frozenset({"APPROVED", "PARTIALLY_RECEIVED"})


def list_receipts(db: Session, *, offset: int = 0, limit: int = 50) -> list[GoodsReceipt]:
    return repository.list_receipts(db, offset=offset, limit=limit)


def get_receipt(db: Session, receipt_id: int) -> GoodsReceipt | None:
    return repository.get_receipt(db, receipt_id)


def get_receipt_options(db: Session) -> GoodsReceiptOptionsResponse:
    orders = repository.list_receivable_orders(db, limit=200)
    options: list[GoodsReceiptOrderOption] = []
    for order in orders:
        supplier = supplier_service.get_supplier(db, order.supplier_id)
        warehouse = warehouse_service.get_warehouse(db, order.warehouse_id)
        if supplier is None or warehouse is None:
            continue
        lines: list[GoodsReceiptOrderLineOption] = []
        for line in order.lines:
            product = product_service.get_product(db, line.product_id)
            if product is None:
                continue
            lines.append(
                GoodsReceiptOrderLineOption(
                    po_line_id=line.id,
                    product_id=line.product_id,
                    product_sku=product.sku,
                    product_name=product.name,
                    unit_code=product.unit.code,
                    allow_decimal=product.unit.allow_decimal,
                    qty_ordered=line.qty,
                    received_qty=line.received_qty,
                    unit_price=line.unit_price,
                )
            )
        options.append(
            GoodsReceiptOrderOption(
                id=order.id,
                doc_no=order.doc_no,
                doc_date=order.doc_date,
                supplier_id=supplier.id,
                supplier_name=supplier.name,
                warehouse_id=warehouse.id,
                warehouse_name=warehouse.name,
                status=order.status,
                lines=lines,
            )
        )
    return GoodsReceiptOptionsResponse(orders=options)


def create_goods_receipt(
    db: Session,
    payload: GoodsReceiptCreate,
    actor: User,
    ip: str | None = None,
) -> GoodsReceipt:
    try:
        order = repository.get_order_for_update(db, payload.po_id)
        if order is None:
            raise HTTPException(status_code=404, detail="Purchase order not found")
        if order.status not in RECEIVABLE_PO_STATUSES:
            raise HTTPException(status_code=409, detail="PURCHASE_ORDER_NOT_RECEIVABLE")
        if warehouse_service.get_active_warehouse(db, order.warehouse_id) is None:
            raise HTTPException(status_code=404, detail="Warehouse not found")
        supplier = supplier_service.get_supplier(db, order.supplier_id)
        if supplier is None or not supplier.is_active or supplier.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Supplier not found")

        tolerance_pct = _get_receipt_tolerance(db)
        po_lines = repository.list_order_lines_for_update(db, order.id)
        if not po_lines:
            raise HTTPException(status_code=409, detail="PURCHASE_ORDER_HAS_NO_LINES")
        po_lines_by_id = {line.id: line for line in po_lines}
        payload_line_ids = [line.po_line_id for line in payload.lines]
        if len(payload_line_ids) != len(set(payload_line_ids)):
            raise HTTPException(
                status_code=422, detail="A purchase order line may appear only once per receipt"
            )
        if any(line_id not in po_lines_by_id for line_id in payload_line_ids):
            raise HTTPException(
                status_code=422,
                detail="Receipt line does not belong to the selected purchase order",
            )

        products = {}
        product_ids = {po_lines_by_id[line_id].product_id for line_id in payload_line_ids}
        for product_id in sorted(product_ids):
            product = product_service.lock_product_for_stock_posting(db, product_id)
            if product is None or not product.is_active or product.deleted_at is not None:
                raise HTTPException(status_code=404, detail="Product not found")
            if not product.is_stocked:
                raise HTTPException(status_code=422, detail="Only stocked products can be received")
            products[product_id] = product

        receipt_lines: list[GoodsReceiptLine] = []
        total = Decimal("0.00")
        incoming_qty: dict[int, Decimal] = {}
        incoming_value: dict[int, Decimal] = {}
        for payload_line in payload.lines:
            po_line = po_lines_by_id[payload_line.po_line_id]
            product = products[po_line.product_id]
            if not payload_line.qty.is_finite() or payload_line.qty <= 0:
                raise HTTPException(status_code=422, detail="Received quantity must be positive")
            if not product.unit.allow_decimal and (
                payload_line.qty != payload_line.qty.to_integral_value()
            ):
                raise HTTPException(
                    status_code=422, detail="Product unit does not allow decimal quantity"
                )
            maximum_received = po_line.qty * (Decimal("1") + tolerance_pct / Decimal("100"))
            if po_line.received_qty + payload_line.qty > maximum_received:
                raise HTTPException(status_code=409, detail="RECEIPT_EXCEEDS_ORDER_TOLERANCE")
            if not payload_line.unit_cost.is_finite() or payload_line.unit_cost < 0:
                raise HTTPException(status_code=422, detail="Unit cost cannot be negative")

            with localcontext() as context:
                context.prec = 40
                line_total = (payload_line.qty * payload_line.unit_cost).quantize(
                    CENT, rounding=ROUND_HALF_UP
                )
            if line_total > MAX_MONEY or total + line_total > MAX_MONEY:
                raise HTTPException(
                    status_code=422,
                    detail="Goods receipt total exceeds supported amount",
                )
            total += line_total
            receipt_lines.append(
                GoodsReceiptLine(
                    po_line_id=po_line.id,
                    product_id=product.id,
                    qty=payload_line.qty,
                    unit_cost=payload_line.unit_cost,
                    line_total=line_total,
                )
            )
            incoming_qty[product.id] = incoming_qty.get(product.id, Decimal("0")) + payload_line.qty
            incoming_value[product.id] = (
                incoming_value.get(product.id, Decimal("0"))
                + payload_line.qty * payload_line.unit_cost
            )

        receipt = GoodsReceipt(
            doc_no=generate_next_number(db, DOCUMENT_TYPE, payload.doc_date.year),
            doc_date=payload.doc_date,
            po_id=order.id,
            supplier_id=order.supplier_id,
            warehouse_id=order.warehouse_id,
            status="POSTED",
            total=total,
            note=payload.note,
            created_by=actor.id,
            lines=receipt_lines,
        )
        db.add(receipt)
        db.flush()

        before_order = _order_snapshot(order)
        lines_by_id = {line.id: line for line in po_lines}
        for receipt_line in receipt.lines:
            po_line = lines_by_id[receipt_line.po_line_id]
            po_line.received_qty += receipt_line.qty
            post_stock_movement(
                db,
                product_id=receipt_line.product_id,
                warehouse_id=order.warehouse_id,
                movement_type=MovementType.PURCHASE_RECEIPT,
                qty_signed=receipt_line.qty,
                unit_cost=receipt_line.unit_cost,
                actor=actor,
                source_type="GOODS_RECEIPT",
                source_id=receipt.id,
                source_line_id=receipt_line.id,
                note=receipt.note,
                txn_date=datetime.combine(payload.doc_date, datetime.min.time(), tzinfo=UTC),
            )

        for product_id, qty in incoming_qty.items():
            product = products[product_id]
            current_qty = get_product_total_on_hand(db, product_id) - qty
            current_average = product.avg_cost
            received_average = incoming_value[product_id] / qty
            product.avg_cost = weighted_average_cost(
                old_qty=current_qty,
                old_avg_cost=current_average,
                received_qty=qty,
                unit_cost=received_average,
            ).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)

        order.status = (
            "RECEIVED"
            if all(line.received_qty >= line.qty for line in po_lines)
            else "PARTIALLY_RECEIVED"
        )
        order.updated_at = datetime.now(UTC)
        db.flush()
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="goods_receipt",
            entity_id=receipt.id,
            action="CREATE",
            after=_receipt_snapshot(receipt),
            ip=ip,
        )
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="purchase_order",
            entity_id=order.id,
            action="STATUS",
            before=before_order,
            after=_order_snapshot(order),
            ip=ip,
        )
        db.commit()
        return repository.get_receipt(db, receipt.id) or receipt
    except Exception:
        db.rollback()
        raise


def list_supplier_due_entries(db: Session, supplier_id: int) -> list[dict[str, object]]:
    return [
        {
            "date": receipt.doc_date.isoformat(),
            "type": "PURCHASE",
            "description": f"Goods Receipt {receipt.doc_no}",
            "amount": receipt.total,
        }
        for receipt in repository.list_receipt_due_entries(db, supplier_id)
    ]


def _get_receipt_tolerance(db: Session) -> Decimal:
    setting = company_settings_service.get_setting(db, "receipt_tolerance_pct")
    if setting is None:
        raise HTTPException(status_code=500, detail="Receiving tolerance is not configured")
    try:
        value = Decimal(setting.value)
    except InvalidOperation as exc:
        raise HTTPException(status_code=500, detail="Receiving tolerance is invalid") from exc
    if not value.is_finite() or value < 0:
        raise HTTPException(status_code=500, detail="Receiving tolerance is invalid")
    return value


def _receipt_snapshot(receipt: GoodsReceipt) -> dict[str, object]:
    return {
        "doc_no": receipt.doc_no,
        "doc_date": receipt.doc_date.isoformat(),
        "po_id": receipt.po_id,
        "supplier_id": receipt.supplier_id,
        "warehouse_id": receipt.warehouse_id,
        "status": receipt.status,
        "total": str(receipt.total),
        "note": receipt.note,
        "lines": [
            {
                "po_line_id": line.po_line_id,
                "product_id": line.product_id,
                "qty": str(line.qty),
                "unit_cost": str(line.unit_cost),
                "line_total": str(line.line_total),
            }
            for line in receipt.lines
        ],
    }


def _order_snapshot(order: PurchaseOrder) -> dict[str, object]:
    return {
        "doc_no": order.doc_no,
        "status": order.status,
        "lines": [
            {
                "id": line.id,
                "product_id": line.product_id,
                "qty": str(line.qty),
                "received_qty": str(line.received_qty),
            }
            for line in order.lines
        ],
    }
