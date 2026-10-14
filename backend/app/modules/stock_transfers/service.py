from datetime import UTC, datetime, time

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.document_numbering.service import generate_next_number
from app.modules.inventory.models import MovementType
from app.modules.inventory.service import post_stock_movement
from app.modules.products import service as product_service
from app.modules.stock_transfers import repository
from app.modules.stock_transfers.models import StockTransfer, StockTransferLine
from app.modules.stock_transfers.schemas import (
    StockTransferCreate,
    StockTransferOptionsResponse,
    TransferProductOption,
    TransferWarehouseOption,
)
from app.modules.warehouses import service as warehouse_service

DOCUMENT_TYPE = "STOCK_TRANSFER"


def list_transfers(db: Session, *, offset: int = 0, limit: int = 50) -> list[StockTransfer]:
    return repository.list_transfers(db, offset=offset, limit=limit)


def get_transfer(db: Session, transfer_id: int) -> StockTransfer | None:
    return repository.get_transfer(db, transfer_id)


def get_transfer_options(db: Session) -> StockTransferOptionsResponse:
    warehouses = warehouse_service.list_warehouses(db, limit=200)
    products = product_service.list_products(db, is_stocked=True, limit=200)
    return StockTransferOptionsResponse(
        warehouses=[
            TransferWarehouseOption(id=item.id, code=item.code, name=item.name)
            for item in warehouses
        ],
        products=[
            TransferProductOption(
                id=item.id,
                sku=item.sku,
                name=item.name,
                unit_code=item.unit.code,
                is_stocked=item.is_stocked,
            )
            for item in products
        ],
    )


def post_transfer(
    db: Session,
    payload: StockTransferCreate,
    actor: User,
    ip: str | None = None,
) -> StockTransfer:
    try:
        if warehouse_service.get_active_warehouse(db, payload.from_warehouse_id) is None:
            raise HTTPException(status_code=404, detail="Source warehouse not found")
        if warehouse_service.get_active_warehouse(db, payload.to_warehouse_id) is None:
            raise HTTPException(status_code=404, detail="Destination warehouse not found")
        if payload.from_warehouse_id == payload.to_warehouse_id:
            raise HTTPException(
                status_code=422, detail="Source and destination warehouses must be different"
            )
        product_ids = [line.product_id for line in payload.lines]
        if len(product_ids) != len(set(product_ids)):
            raise HTTPException(
                status_code=422, detail="A product may appear only once in a transfer"
            )

        for payload_line in payload.lines:
            product = product_service.get_product(db, payload_line.product_id)
            if product is None or not product.is_active or product.deleted_at is not None:
                raise HTTPException(status_code=404, detail="Product not found")
            if not product.is_stocked:
                raise HTTPException(
                    status_code=422, detail="Only stocked products can be transferred"
                )

        transfer = StockTransfer(
            doc_no=generate_next_number(db, DOCUMENT_TYPE, payload.doc_date.year),
            doc_date=payload.doc_date,
            from_warehouse_id=payload.from_warehouse_id,
            to_warehouse_id=payload.to_warehouse_id,
            status="POSTED",
            note=payload.note,
            lines=[
                StockTransferLine(product_id=line.product_id, qty=line.qty)
                for line in payload.lines
            ],
        )
        db.add(transfer)
        db.flush()

        posted_at = datetime.combine(payload.doc_date, time.min, tzinfo=UTC)
        for transfer_line in sorted(transfer.lines, key=lambda item: item.product_id):
            post_stock_movement(
                db,
                product_id=transfer_line.product_id,
                warehouse_id=transfer.from_warehouse_id,
                movement_type=MovementType.TRANSFER_OUT,
                qty_signed=-transfer_line.qty,
                actor=actor,
                source_type=DOCUMENT_TYPE,
                source_id=transfer.id,
                source_line_id=transfer_line.id,
                note=transfer.note,
                txn_date=posted_at,
            )
            post_stock_movement(
                db,
                product_id=transfer_line.product_id,
                warehouse_id=transfer.to_warehouse_id,
                movement_type=MovementType.TRANSFER_IN,
                qty_signed=transfer_line.qty,
                actor=actor,
                source_type=DOCUMENT_TYPE,
                source_id=transfer.id,
                source_line_id=transfer_line.id,
                note=transfer.note,
                txn_date=posted_at,
            )

        record_audit(
            db,
            actor_id=actor.id,
            entity_type="stock_transfer",
            entity_id=transfer.id,
            action="CREATE",
            after=_snapshot(transfer),
            ip=ip,
        )
        db.commit()
        db.refresh(transfer)
        return transfer
    except Exception:
        db.rollback()
        raise


def _snapshot(transfer: StockTransfer) -> dict[str, object]:
    return {
        "doc_no": transfer.doc_no,
        "doc_date": transfer.doc_date.isoformat(),
        "from_warehouse_id": transfer.from_warehouse_id,
        "to_warehouse_id": transfer.to_warehouse_id,
        "status": transfer.status,
        "note": transfer.note,
        "lines": [
            {"id": line.id, "product_id": line.product_id, "qty": str(line.qty)}
            for line in transfer.lines
        ],
    }
