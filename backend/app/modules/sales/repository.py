from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.sales.models import SalesOrder, SalesOrderLine


def get_order_line_for_update(
    db: Session, sales_order_line_id: int
) -> tuple[SalesOrderLine, SalesOrder] | None:
    line = db.scalar(
        select(SalesOrderLine).where(SalesOrderLine.id == sales_order_line_id).with_for_update()
    )
    if line is None:
        return None
    order = db.scalar(select(SalesOrder).where(SalesOrder.id == line.order_id).with_for_update())
    if order is None:
        return None
    return line, order
