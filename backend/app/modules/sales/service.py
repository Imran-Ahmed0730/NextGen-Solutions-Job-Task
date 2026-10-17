from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.sales import repository
from app.modules.sales.models import SalesOrder, SalesOrderLine


def lock_order_line_for_reservation(
    db: Session, sales_order_line_id: int
) -> tuple[SalesOrderLine, SalesOrder] | None:
    return repository.get_order_line_for_update(db, sales_order_line_id)


def adjust_reserved_quantity(
    db: Session,
    *,
    line: SalesOrderLine,
    quantity_delta: Decimal,
    actor: User,
    ip: str | None = None,
) -> None:
    before: dict[str, object] = {"qty_reserved": str(line.qty_reserved)}
    new_quantity = line.qty_reserved + quantity_delta
    if new_quantity < 0:
        raise HTTPException(status_code=409, detail="RESERVATION_BALANCE_INVALID")
    line.qty_reserved = new_quantity
    db.flush()
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="sales_order_line",
        entity_id=line.id,
        action="UPDATE",
        before=before,
        after={"qty_reserved": str(line.qty_reserved)},
        ip=ip,
    )
    db.flush()


def consume_reserved_quantity(
    db: Session,
    *,
    line: SalesOrderLine,
    quantity: Decimal,
    actor: User,
    ip: str | None = None,
) -> None:
    before: dict[str, object] = {
        "qty_reserved": str(line.qty_reserved),
        "qty_delivered": str(line.qty_delivered),
    }
    new_reserved = line.qty_reserved - quantity
    new_delivered = line.qty_delivered + quantity
    if new_reserved < 0 or new_delivered > line.qty_ordered:
        raise HTTPException(status_code=409, detail="RESERVATION_BALANCE_INVALID")
    line.qty_reserved = new_reserved
    line.qty_delivered = new_delivered
    db.flush()
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="sales_order_line",
        entity_id=line.id,
        action="UPDATE",
        before=before,
        after={
            "qty_reserved": str(line.qty_reserved),
            "qty_delivered": str(line.qty_delivered),
        },
        ip=ip,
    )
    db.flush()


def record_unreserved_delivery_quantity(
    db: Session,
    *,
    line: SalesOrderLine,
    quantity: Decimal,
    actor: User,
    ip: str | None = None,
) -> None:
    before: dict[str, object] = {"qty_delivered": str(line.qty_delivered)}
    new_delivered = line.qty_delivered + quantity
    if quantity <= 0 or new_delivered > line.qty_ordered:
        raise HTTPException(status_code=409, detail="DELIVERY_EXCEEDS_ORDER_REMAINING")
    line.qty_delivered = new_delivered
    db.flush()
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="sales_order_line",
        entity_id=line.id,
        action="UPDATE",
        before=before,
        after={"qty_delivered": str(line.qty_delivered)},
        ip=ip,
    )
    db.flush()
