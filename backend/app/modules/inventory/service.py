from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.inventory import repository
from app.modules.inventory.models import MovementType, StockBalance, StockTransaction
from app.modules.inventory.schemas import (
    StockLedgerEntryResponse,
    StockLedgerOptionsResponse,
    StockLedgerProductOption,
    StockLedgerWarehouseOption,
    WarehouseStockResponse,
)
from app.modules.products import service as product_service
from app.modules.warehouses import service as warehouse_service

INBOUND_MOVEMENTS = frozenset(
    {
        MovementType.PURCHASE_RECEIPT,
        MovementType.PRODUCTION_OUTPUT,
        MovementType.SALE_RETURN,
        MovementType.TRANSFER_IN,
        MovementType.ADJUSTMENT_IN,
        MovementType.OPENING,
    }
)
OUTBOUND_MOVEMENTS = frozenset(
    {
        MovementType.PURCHASE_RETURN,
        MovementType.PRODUCTION_CONSUME,
        MovementType.SALE_DELIVERY,
        MovementType.TRANSFER_OUT,
        MovementType.ADJUSTMENT_OUT,
    }
)
QUANTITY_SCALE = Decimal("0.001")
MAX_QUANTITY = Decimal("999999999999999.999")
MAX_UNIT_COST = Decimal("99999999999999.9999")


def weighted_average_cost(
    *, old_qty: Decimal, old_avg_cost: Decimal, received_qty: Decimal, unit_cost: Decimal
) -> Decimal:
    values = (old_qty, old_avg_cost, received_qty, unit_cost)
    if any(not isinstance(value, Decimal) or not value.is_finite() for value in values):
        raise HTTPException(status_code=422, detail="Costing values must be finite decimals")
    if old_qty < 0 or received_qty <= 0 or old_avg_cost < 0 or unit_cost < 0:
        raise HTTPException(status_code=422, detail="Costing values cannot be negative")
    total_qty = old_qty + received_qty
    return (old_qty * old_avg_cost + received_qty * unit_cost) / total_qty


def post_stock_movement(
    db: Session,
    *,
    product_id: int,
    warehouse_id: int,
    movement_type: MovementType,
    qty_signed: Decimal,
    actor: User,
    unit_cost: Decimal | None = None,
    source_type: str | None = None,
    source_id: int | None = None,
    source_line_id: int | None = None,
    note: str | None = None,
    txn_date: datetime | None = None,
) -> StockTransaction:
    if not isinstance(movement_type, MovementType):
        raise HTTPException(status_code=422, detail="Invalid stock movement type")
    _validate_quantity(qty_signed)
    _validate_movement_sign(movement_type, qty_signed)
    if unit_cost is not None:
        _validate_unit_cost(unit_cost)
    if source_type is not None and (not source_type.strip() or len(source_type) > 50):
        raise HTTPException(status_code=422, detail="Source type must be 1 to 50 characters")
    if source_id is not None and (isinstance(source_id, bool) or source_id <= 0):
        raise HTTPException(status_code=422, detail="Source ID must be a positive integer")
    if source_line_id is not None and (isinstance(source_line_id, bool) or source_line_id <= 0):
        raise HTTPException(status_code=422, detail="Source line ID must be a positive integer")
    if txn_date is not None and txn_date.tzinfo is None:
        raise HTTPException(status_code=422, detail="Transaction date must include a timezone")

    product = product_service.lock_product_for_stock_posting(db, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    warehouse = warehouse_service.get_warehouse(db, warehouse_id)
    if warehouse is None:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    if not product.unit.allow_decimal and qty_signed != qty_signed.to_integral_value():
        raise HTTPException(status_code=422, detail="Product unit does not allow decimal quantity")

    balance = repository.get_balance(db, product_id, warehouse_id, for_update=True)
    if balance is None:
        balance = StockBalance(
            product_id=product_id,
            warehouse_id=warehouse_id,
            qty_on_hand=Decimal("0.000"),
            qty_reserved=Decimal("0.000"),
        )
        db.add(balance)

    resulting_qty = balance.qty_on_hand + qty_signed
    if product.is_stocked and (resulting_qty < 0 or resulting_qty < balance.qty_reserved):
        raise HTTPException(status_code=409, detail="STOCK_INSUFFICIENT")

    posted_at = txn_date or datetime.now(UTC)
    transaction = StockTransaction(
        txn_date=posted_at,
        product_id=product_id,
        warehouse_id=warehouse_id,
        movement_type=movement_type,
        qty_signed=qty_signed,
        unit_cost=unit_cost,
        source_type=source_type.strip() if source_type else None,
        source_id=source_id,
        source_line_id=source_line_id,
        note=note,
        created_by=actor.id,
    )
    balance.qty_on_hand = resulting_qty
    balance.updated_at = posted_at
    db.add(transaction)
    db.flush()

    record_audit(
        db,
        actor_id=actor.id,
        entity_type="stock_transaction",
        entity_id=transaction.id,
        action="CREATE",
        after=_snapshot(transaction),
    )
    db.flush()
    return transaction


def list_stock(
    db: Session,
    *,
    product_id: int | None = None,
    warehouse_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
) -> list[StockBalance]:
    return repository.list_balances(
        db,
        product_id=product_id,
        warehouse_id=warehouse_id,
        offset=offset,
        limit=limit,
    )


def list_warehouse_stock(
    db: Session,
    *,
    search: str | None = None,
    warehouse_id: int | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[WarehouseStockResponse]:
    normalized_search = (search or "").strip() or None
    warehouses = []
    warehouse_offset = 0
    while True:
        warehouse_page = warehouse_service.list_warehouses(db, offset=warehouse_offset, limit=200)
        warehouses.extend(warehouse_page)
        if len(warehouse_page) < 200:
            break
        warehouse_offset += 200
    if warehouse_id is not None:
        warehouses = [warehouse for warehouse in warehouses if warehouse.id == warehouse_id]
    if not warehouses:
        return []

    product_count = product_service.count_stocked_products(db, search=normalized_search)
    if product_count == 0 or offset >= product_count * len(warehouses):
        return []

    warehouse_count = len(warehouses)
    first_product = offset // warehouse_count
    first_warehouse = offset % warehouse_count
    product_limit = min(
        product_count - first_product,
        (first_warehouse + limit + warehouse_count - 1) // warehouse_count,
    )
    products = product_service.list_products(
        db,
        search=normalized_search,
        is_stocked=True,
        offset=first_product,
        limit=product_limit,
    )
    balances = repository.list_balances_for_products(
        db,
        product_ids=[product.id for product in products],
        warehouse_ids=[warehouse.id for warehouse in warehouses],
    )
    balance_by_pair = {(balance.product_id, balance.warehouse_id): balance for balance in balances}

    result: list[WarehouseStockResponse] = []
    for product_index, product in enumerate(products, start=first_product):
        for warehouse_index, warehouse in enumerate(warehouses):
            row_offset = product_index * warehouse_count + warehouse_index
            if row_offset < offset or row_offset >= offset + limit:
                continue
            balance = balance_by_pair.get((product.id, warehouse.id))
            qty_on_hand = balance.qty_on_hand if balance is not None else Decimal("0.000")
            qty_reserved = balance.qty_reserved if balance is not None else Decimal("0.000")
            result.append(
                WarehouseStockResponse(
                    product_id=product.id,
                    product_sku=product.sku,
                    product_name=product.name,
                    unit_code=product.unit.code,
                    warehouse_id=warehouse.id,
                    warehouse_code=warehouse.code,
                    warehouse_name=warehouse.name,
                    qty_on_hand=qty_on_hand,
                    qty_reserved=qty_reserved,
                    available=qty_on_hand - qty_reserved,
                )
            )
    return result


def list_stock_ledger(
    db: Session,
    *,
    product_id: int,
    warehouse_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    offset: int = 0,
    limit: int = 100,
) -> list[StockLedgerEntryResponse]:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(status_code=422, detail="Start date cannot be after end date")
    date_from_bound = datetime.combine(date_from, time.min) if date_from else None
    date_to_bound = datetime.combine(date_to + timedelta(days=1), time.min) if date_to else None
    entries = repository.list_ledger_entries(
        db,
        product_id=product_id,
        warehouse_id=warehouse_id,
        date_from=date_from_bound,
        date_to_exclusive=date_to_bound,
        offset=offset,
        limit=limit,
    )
    return [
        StockLedgerEntryResponse(
            id=transaction.id,
            txn_date=transaction.txn_date,
            product_id=transaction.product_id,
            warehouse_id=transaction.warehouse_id,
            movement_type=transaction.movement_type,
            qty_signed=transaction.qty_signed,
            unit_cost=transaction.unit_cost,
            source_type=transaction.source_type,
            source_id=transaction.source_id,
            source_line_id=transaction.source_line_id,
            note=transaction.note,
            created_by=transaction.created_by,
            created_at=transaction.created_at,
            running_qty=running_qty,
        )
        for transaction, running_qty in entries
    ]


def get_stock_ledger_options(db: Session) -> StockLedgerOptionsResponse:
    warehouses = warehouse_service.list_warehouses(db, limit=200)
    products = product_service.list_products(db, is_stocked=True, limit=200)
    return StockLedgerOptionsResponse(
        products=[
            StockLedgerProductOption(
                id=product.id,
                sku=product.sku,
                name=product.name,
                unit_code=product.unit.code,
            )
            for product in products
        ],
        warehouses=[
            StockLedgerWarehouseOption(id=warehouse.id, code=warehouse.code, name=warehouse.name)
            for warehouse in warehouses
        ],
    )


def _validate_quantity(value: Decimal) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise HTTPException(status_code=422, detail="Quantity must be a finite decimal")
    if value == 0:
        raise HTTPException(status_code=422, detail="Quantity cannot be zero")
    if abs(value) > MAX_QUANTITY:
        raise HTTPException(status_code=422, detail="Quantity exceeds supported precision")
    if value != value.quantize(QUANTITY_SCALE):
        raise HTTPException(status_code=422, detail="Quantity supports at most 3 decimal places")


def _validate_unit_cost(value: Decimal) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise HTTPException(status_code=422, detail="Unit cost must be a nonnegative decimal")
    if value > MAX_UNIT_COST or value != value.quantize(Decimal("0.0001")):
        raise HTTPException(status_code=422, detail="Unit cost supports at most 4 decimal places")


def _validate_movement_sign(movement_type: MovementType, qty_signed: Decimal) -> None:
    if movement_type in INBOUND_MOVEMENTS and qty_signed < 0:
        raise HTTPException(status_code=422, detail="Movement quantity must be positive")
    if movement_type in OUTBOUND_MOVEMENTS and qty_signed > 0:
        raise HTTPException(status_code=422, detail="Movement quantity must be negative")


def _snapshot(transaction: StockTransaction) -> dict[str, object]:
    return {
        "txn_date": transaction.txn_date.isoformat(),
        "product_id": transaction.product_id,
        "warehouse_id": transaction.warehouse_id,
        "movement_type": transaction.movement_type.value,
        "qty_signed": str(transaction.qty_signed),
        "unit_cost": str(transaction.unit_cost) if transaction.unit_cost is not None else None,
        "source_type": transaction.source_type,
        "source_id": transaction.source_id,
        "source_line_id": transaction.source_line_id,
        "note": transaction.note,
    }
