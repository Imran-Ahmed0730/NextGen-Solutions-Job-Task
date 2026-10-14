from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, localcontext

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.document_numbering.service import generate_next_number
from app.modules.goods_receipts import service as goods_receipt_service
from app.modules.inventory.models import MovementType
from app.modules.inventory.service import post_stock_movement
from app.modules.products import service as product_service
from app.modules.purchase_returns import repository
from app.modules.purchase_returns.models import PurchaseReturn, PurchaseReturnLine
from app.modules.purchase_returns.schemas import (
    PurchaseReturnCreate,
    PurchaseReturnOptionsResponse,
    PurchaseReturnReceiptLineOption,
    PurchaseReturnReceiptOption,
)
from app.modules.suppliers import service as supplier_service
from app.modules.warehouses import service as warehouse_service

DOCUMENT_TYPE = "PURCHASE_RETURN"
CENT = Decimal("0.01")
MAX_MONEY = Decimal("9999999999999999.99")


def list_purchase_returns(db: Session, *, offset: int = 0, limit: int = 50) -> list[PurchaseReturn]:
    return repository.list_purchase_returns(db, offset=offset, limit=limit)


def get_purchase_return(db: Session, return_id: int) -> PurchaseReturn | None:
    return repository.get_purchase_return(db, return_id)


def get_purchase_return_options(db: Session) -> PurchaseReturnOptionsResponse:
    receipts = goods_receipt_service.list_receipts(db, offset=0, limit=200)
    returned_quantities = repository.get_returned_quantities(
        db, [receipt.id for receipt in receipts]
    )
    options: list[PurchaseReturnReceiptOption] = []
    for receipt in receipts:
        supplier = supplier_service.get_supplier(db, receipt.supplier_id)
        warehouse = warehouse_service.get_warehouse(db, receipt.warehouse_id)
        if supplier is None or warehouse is None:
            continue
        lines: list[PurchaseReturnReceiptLineOption] = []
        for line in receipt.lines:
            qty_returned = returned_quantities.get(line.id, Decimal("0.000"))
            qty_available = line.qty - qty_returned
            if qty_available <= 0:
                continue
            product = line.product
            lines.append(
                PurchaseReturnReceiptLineOption(
                    receipt_line_id=line.id,
                    product_id=product.id,
                    product_sku=product.sku,
                    product_name=product.name,
                    unit_code=product.unit.code,
                    allow_decimal=product.unit.allow_decimal,
                    qty_received=line.qty,
                    qty_returned=qty_returned,
                    qty_available=qty_available,
                    unit_cost=line.unit_cost,
                )
            )
        if lines:
            options.append(
                PurchaseReturnReceiptOption(
                    id=receipt.id,
                    doc_no=receipt.doc_no,
                    doc_date=receipt.doc_date,
                    supplier_id=supplier.id,
                    supplier_name=supplier.name,
                    warehouse_id=warehouse.id,
                    warehouse_name=warehouse.name,
                    lines=lines,
                )
            )
    return PurchaseReturnOptionsResponse(receipts=options)


def create_purchase_return(
    db: Session,
    payload: PurchaseReturnCreate,
    actor: User,
    ip: str | None = None,
) -> PurchaseReturn:
    try:
        receipt = goods_receipt_service.get_receipt_for_purchase_return(db, payload.receipt_id)
        if receipt is None:
            raise HTTPException(status_code=404, detail="Goods receipt not found")
        if receipt.status != "POSTED":
            raise HTTPException(status_code=409, detail="GOODS_RECEIPT_NOT_RETURNABLE")
        receipt_lines = goods_receipt_service.list_receipt_lines_for_purchase_return(db, receipt.id)
        if not receipt_lines:
            raise HTTPException(status_code=409, detail="GOODS_RECEIPT_HAS_NO_LINES")
        receipt_lines_by_id = {line.id: line for line in receipt_lines}
        payload_line_ids = [line.receipt_line_id for line in payload.lines]
        if len(payload_line_ids) != len(set(payload_line_ids)):
            raise HTTPException(
                status_code=422, detail="A receipt line may appear only once per return"
            )
        if any(line_id not in receipt_lines_by_id for line_id in payload_line_ids):
            raise HTTPException(
                status_code=422,
                detail="Return line does not belong to the selected goods receipt",
            )

        existing_lines = repository.list_existing_return_lines_for_update(db, receipt.id)
        returned_by_line: dict[int, Decimal] = {}
        for existing_line in existing_lines:
            returned_by_line[existing_line.receipt_line_id] = (
                returned_by_line.get(existing_line.receipt_line_id, Decimal("0.000"))
                + existing_line.qty
            )
        product_ids = sorted(
            {receipt_lines_by_id[line_id].product_id for line_id in payload_line_ids}
        )
        products = {}
        for product_id in product_ids:
            product = product_service.lock_product_for_stock_posting(db, product_id)
            if product is None:
                raise HTTPException(status_code=404, detail="Product not found")
            products[product_id] = product

        return_lines: list[PurchaseReturnLine] = []
        total = Decimal("0.00")
        for payload_line in payload.lines:
            receipt_line = receipt_lines_by_id[payload_line.receipt_line_id]
            product = products[receipt_line.product_id]
            if not payload_line.qty.is_finite() or payload_line.qty <= 0:
                raise HTTPException(status_code=422, detail="Return quantity must be positive")
            if not product.unit.allow_decimal and (
                payload_line.qty != payload_line.qty.to_integral_value()
            ):
                raise HTTPException(
                    status_code=422, detail="Product unit does not allow decimal quantity"
                )
            qty_available = receipt_line.qty - returned_by_line.get(
                receipt_line.id, Decimal("0.000")
            )
            if payload_line.qty > qty_available:
                raise HTTPException(status_code=409, detail="PURCHASE_RETURN_EXCEEDS_RECEIVED_QTY")
            with localcontext() as context:
                context.prec = 40
                line_total = (payload_line.qty * receipt_line.unit_cost).quantize(
                    CENT, rounding=ROUND_HALF_UP
                )
            if line_total > MAX_MONEY or total + line_total > MAX_MONEY:
                raise HTTPException(
                    status_code=422,
                    detail="Purchase return total exceeds supported amount",
                )
            total += line_total
            return_lines.append(
                PurchaseReturnLine(
                    receipt_line_id=receipt_line.id,
                    product_id=product.id,
                    qty=payload_line.qty,
                    unit_cost=receipt_line.unit_cost,
                    line_total=line_total,
                )
            )

        purchase_return = PurchaseReturn(
            doc_no=generate_next_number(db, DOCUMENT_TYPE, payload.doc_date.year),
            doc_date=payload.doc_date,
            receipt_id=receipt.id,
            supplier_id=receipt.supplier_id,
            warehouse_id=receipt.warehouse_id,
            status="POSTED",
            total=total,
            note=payload.note,
            created_by=actor.id,
            lines=return_lines,
        )
        db.add(purchase_return)
        db.flush()

        for return_line in purchase_return.lines:
            post_stock_movement(
                db,
                product_id=return_line.product_id,
                warehouse_id=purchase_return.warehouse_id,
                movement_type=MovementType.PURCHASE_RETURN,
                qty_signed=-return_line.qty,
                unit_cost=return_line.unit_cost,
                actor=actor,
                source_type="PURCHASE_RETURN",
                source_id=purchase_return.id,
                source_line_id=return_line.id,
                note=purchase_return.note,
                txn_date=datetime.combine(payload.doc_date, datetime.min.time(), tzinfo=UTC),
            )

        db.flush()
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="purchase_return",
            entity_id=purchase_return.id,
            action="CREATE",
            after=_snapshot(purchase_return),
            ip=ip,
        )
        db.commit()
        return repository.get_purchase_return(db, purchase_return.id) or purchase_return
    except Exception:
        db.rollback()
        raise


def list_supplier_due_entries(db: Session, supplier_id: int) -> list[dict[str, object]]:
    return [
        {
            "date": purchase_return.doc_date.isoformat(),
            "type": "PURCHASE_RETURN",
            "description": f"Purchase Return {purchase_return.doc_no}",
            "amount": -purchase_return.total,
        }
        for purchase_return in repository.list_supplier_due_entries(db, supplier_id)
    ]


def _snapshot(purchase_return: PurchaseReturn) -> dict[str, object]:
    return {
        "doc_no": purchase_return.doc_no,
        "doc_date": purchase_return.doc_date.isoformat(),
        "receipt_id": purchase_return.receipt_id,
        "supplier_id": purchase_return.supplier_id,
        "warehouse_id": purchase_return.warehouse_id,
        "status": purchase_return.status,
        "total": str(purchase_return.total),
        "note": purchase_return.note,
        "lines": [
            {
                "receipt_line_id": line.receipt_line_id,
                "product_id": line.product_id,
                "qty": str(line.qty),
                "unit_cost": str(line.unit_cost),
                "line_total": str(line.line_total),
            }
            for line in purchase_return.lines
        ],
    }
