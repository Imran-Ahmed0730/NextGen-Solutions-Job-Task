from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, localcontext

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.direct_purchases import repository
from app.modules.direct_purchases.models import DirectPurchase, DirectPurchaseLine
from app.modules.direct_purchases.schemas import (
    DirectPurchaseCreate,
    DirectPurchaseOptionsResponse,
    DirectPurchaseProductOption,
    DirectPurchaseSupplierOption,
    DirectPurchaseWarehouseOption,
)
from app.modules.document_numbering.service import generate_next_number
from app.modules.inventory.models import MovementType
from app.modules.inventory.service import (
    get_product_total_on_hand,
    post_stock_movement,
    weighted_average_cost,
)
from app.modules.products import service as product_service
from app.modules.products.models import Product
from app.modules.suppliers import service as supplier_service
from app.modules.warehouses import service as warehouse_service

DOCUMENT_TYPE = "DIRECT_PURCHASE"
CENT = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")
MAX_MONEY = Decimal("9999999999999999.99")


def list_direct_purchases(db: Session, *, offset: int = 0, limit: int = 50) -> list[DirectPurchase]:
    return repository.list_direct_purchases(db, offset=offset, limit=limit)


def get_direct_purchase(db: Session, purchase_id: int) -> DirectPurchase | None:
    return repository.get_direct_purchase(db, purchase_id)


def get_direct_purchase_options(db: Session) -> DirectPurchaseOptionsResponse:
    suppliers = supplier_service.list_suppliers(limit=200, db=db)
    warehouses = warehouse_service.list_warehouses(limit=200, db=db)
    products = product_service.list_products(limit=200, is_stocked=True, db=db)
    return DirectPurchaseOptionsResponse(
        suppliers=[
            DirectPurchaseSupplierOption(id=item.id, code=item.code, name=item.name)
            for item in suppliers
        ],
        warehouses=[
            DirectPurchaseWarehouseOption(id=item.id, code=item.code, name=item.name)
            for item in warehouses
        ],
        products=[
            DirectPurchaseProductOption(
                id=item.id,
                sku=item.sku,
                name=item.name,
                unit_code=item.unit.code,
                allow_decimal=item.unit.allow_decimal,
            )
            for item in products
        ],
    )


def create_direct_purchase(
    db: Session,
    payload: DirectPurchaseCreate,
    actor: User,
    ip: str | None = None,
) -> DirectPurchase:
    try:
        supplier = supplier_service.get_supplier(db, payload.supplier_id)
        if supplier is None or not supplier.is_active or supplier.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Supplier not found")
        if warehouse_service.get_active_warehouse(db, payload.warehouse_id) is None:
            raise HTTPException(status_code=404, detail="Warehouse not found")

        products: dict[int, Product] = {}
        for product_id in sorted({line.product_id for line in payload.lines}):
            product = product_service.lock_product_for_stock_posting(db, product_id)
            if product is None or not product.is_active or product.deleted_at is not None:
                raise HTTPException(status_code=404, detail="Product not found")
            if not product.is_stocked:
                raise HTTPException(
                    status_code=422, detail="Only stocked products can be purchased"
                )
            products[product_id] = product

        purchase_lines: list[DirectPurchaseLine] = []
        total = Decimal("0.00")
        incoming_qty: dict[int, Decimal] = {}
        incoming_value: dict[int, Decimal] = {}
        for payload_line in payload.lines:
            product = products[payload_line.product_id]
            if not payload_line.qty.is_finite() or payload_line.qty <= 0:
                raise HTTPException(status_code=422, detail="Purchase quantity must be positive")
            if not product.unit.allow_decimal and (
                payload_line.qty != payload_line.qty.to_integral_value()
            ):
                raise HTTPException(
                    status_code=422, detail="Product unit does not allow decimal quantity"
                )
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
                    detail="Direct purchase total exceeds supported amount",
                )
            total += line_total
            purchase_lines.append(
                DirectPurchaseLine(
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

        purchase = DirectPurchase(
            doc_no=generate_next_number(db, DOCUMENT_TYPE, payload.doc_date.year),
            doc_date=payload.doc_date,
            supplier_id=supplier.id,
            warehouse_id=payload.warehouse_id,
            status="POSTED",
            total=total,
            paid_amount=Decimal("0.00"),
            money_account_id=None,
            note=payload.note,
            created_by=actor.id,
            lines=purchase_lines,
        )
        db.add(purchase)
        db.flush()

        for purchase_line in purchase.lines:
            post_stock_movement(
                db,
                product_id=purchase_line.product_id,
                warehouse_id=purchase.warehouse_id,
                movement_type=MovementType.PURCHASE_RECEIPT,
                qty_signed=purchase_line.qty,
                unit_cost=purchase_line.unit_cost,
                actor=actor,
                source_type="DIRECT_PURCHASE",
                source_id=purchase.id,
                source_line_id=purchase_line.id,
                note=purchase.note,
                txn_date=datetime.combine(payload.doc_date, datetime.min.time(), tzinfo=UTC),
            )

        for product_id, qty in incoming_qty.items():
            product = products[product_id]
            current_qty = get_product_total_on_hand(db, product_id) - qty
            received_average = incoming_value[product_id] / qty
            product.avg_cost = weighted_average_cost(
                old_qty=current_qty,
                old_avg_cost=product.avg_cost,
                received_qty=qty,
                unit_cost=received_average,
            ).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)

        db.flush()
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="direct_purchase",
            entity_id=purchase.id,
            action="CREATE",
            after=_snapshot(purchase),
            ip=ip,
        )
        db.commit()
        return repository.get_direct_purchase(db, purchase.id) or purchase
    except Exception:
        db.rollback()
        raise


def list_supplier_due_entries(db: Session, supplier_id: int) -> list[dict[str, object]]:
    return [
        {
            "date": purchase.doc_date.isoformat(),
            "type": "PURCHASE",
            "description": f"Direct Purchase {purchase.doc_no}",
            "amount": purchase.total,
        }
        for purchase in repository.list_supplier_due_entries(db, supplier_id)
    ]


def _snapshot(purchase: DirectPurchase) -> dict[str, object]:
    return {
        "doc_no": purchase.doc_no,
        "doc_date": purchase.doc_date.isoformat(),
        "supplier_id": purchase.supplier_id,
        "warehouse_id": purchase.warehouse_id,
        "status": purchase.status,
        "total": str(purchase.total),
        "paid_amount": str(purchase.paid_amount),
        "money_account_id": purchase.money_account_id,
        "note": purchase.note,
        "lines": [
            {
                "product_id": line.product_id,
                "qty": str(line.qty),
                "unit_cost": str(line.unit_cost),
                "line_total": str(line.line_total),
            }
            for line in purchase.lines
        ],
    }
