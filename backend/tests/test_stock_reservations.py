from collections.abc import Generator
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.modules.auth.models import AuditLog, User
from app.modules.auth.seed import seed_initial_admin
from app.modules.customers.models import Customer
from app.modules.inventory.models import (
    MovementType,
    StockBalance,
    StockReservation,
    StockTransaction,
)
from app.modules.inventory.service import (
    consume_reservation,
    post_stock_movement,
    release_reservation,
    reserve_stock,
)
from app.modules.product_categories.models import ProductCategory
from app.modules.products.models import Product, ProductType
from app.modules.sales.models import SalesOrder, SalesOrderLine
from app.modules.units.models import Unit
from app.modules.warehouses.models import Warehouse


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        yield session
    engine.dispose()


@pytest.fixture
def reservation_fixture(
    db_session: Session,
) -> tuple[User, Product, Warehouse, SalesOrderLine]:
    seed_result = seed_initial_admin(db_session)
    actor = db_session.scalar(select(User).where(User.username == seed_result.username))
    assert actor is not None
    customer = Customer(code="C-001", name="Customer")
    category = ProductCategory(name="Finished Goods")
    unit = Unit(name="Each", code="ea", allow_decimal=True)
    warehouse = Warehouse(name="Main Warehouse", code="MAIN")
    db_session.add_all([customer, category, unit, warehouse])
    db_session.flush()
    product = Product(
        sku="FG-001",
        name="Finished Product",
        type=ProductType.FINISHED,
        category_id=category.id,
        unit_id=unit.id,
        is_stocked=True,
        avg_cost=Decimal("2.5000"),
    )
    db_session.add(product)
    db_session.flush()
    order = SalesOrder(
        doc_no="SO-20260001",
        doc_date=date(2026, 10, 14),
        customer_id=customer.id,
        warehouse_id=warehouse.id,
        status="DRAFT",
    )
    db_session.add(order)
    db_session.flush()
    line = SalesOrderLine(
        order_id=order.id,
        product_id=product.id,
        qty_ordered=Decimal("10.000"),
        unit_price=Decimal("5.00"),
        line_total=Decimal("50.00"),
    )
    db_session.add(line)
    db_session.flush()
    post_stock_movement(
        db_session,
        product_id=product.id,
        warehouse_id=warehouse.id,
        movement_type=MovementType.OPENING,
        qty_signed=Decimal("10.000"),
        actor=actor,
        unit_cost=Decimal("2.5000"),
    )
    db_session.commit()
    db_session.refresh(line)
    db_session.refresh(warehouse)
    return actor, product, warehouse, line


def test_reserve_changes_available_not_on_hand_or_ledger(
    db_session: Session,
    reservation_fixture: tuple[User, Product, Warehouse, SalesOrderLine],
) -> None:
    actor, product, warehouse, line = reservation_fixture

    reservation = reserve_stock(
        db_session,
        sales_order_line_id=line.id,
        qty=Decimal("6.000"),
        actor=actor,
    )
    db_session.commit()

    balance = db_session.get(StockBalance, (product.id, warehouse.id))
    assert balance is not None
    assert balance.qty_on_hand == Decimal("10.000")
    assert balance.qty_reserved == Decimal("6.000")
    assert balance.available == Decimal("4.000")
    assert line.qty_reserved == Decimal("6.000")
    assert reservation.status == "ACTIVE"
    assert reservation.qty_consumed == Decimal("0.000")
    assert reservation.qty_released == Decimal("0.000")
    assert db_session.scalar(select(func.count(StockTransaction.id))) == 1
    assert (
        db_session.scalar(
            select(func.count(AuditLog.id)).where(AuditLog.entity_type == "stock_reservation")
        )
        == 1
    )


def test_reservation_rejects_unavailable_or_excess_order_quantity(
    db_session: Session,
    reservation_fixture: tuple[User, Product, Warehouse, SalesOrderLine],
) -> None:
    actor, _, _, line = reservation_fixture
    line.qty_ordered = Decimal("12.000")
    db_session.flush()

    with pytest.raises(HTTPException) as insufficient:
        reserve_stock(
            db_session,
            sales_order_line_id=line.id,
            qty=Decimal("11.000"),
            actor=actor,
        )
    assert insufficient.value.status_code == 409
    assert insufficient.value.detail == "STOCK_INSUFFICIENT"
    db_session.rollback()

    line = db_session.get(SalesOrderLine, line.id)
    assert line is not None
    reservation = reserve_stock(
        db_session,
        sales_order_line_id=line.id,
        qty=Decimal("10.000"),
        actor=actor,
    )
    db_session.flush()
    with pytest.raises(HTTPException) as exceeds_order:
        reserve_stock(
            db_session,
            sales_order_line_id=line.id,
            qty=Decimal("0.001"),
            actor=actor,
        )
    assert exceeds_order.value.status_code == 409
    assert exceeds_order.value.detail == "RESERVATION_EXCEEDS_ORDER_REMAINING"
    db_session.rollback()
    assert db_session.get(StockReservation, reservation.id) is None


def test_partial_release_keeps_reservation_active_until_remainder_is_released(
    db_session: Session,
    reservation_fixture: tuple[User, Product, Warehouse, SalesOrderLine],
) -> None:
    actor, product, warehouse, line = reservation_fixture
    reservation = reserve_stock(
        db_session,
        sales_order_line_id=line.id,
        qty=Decimal("6.000"),
        actor=actor,
    )
    db_session.commit()

    reservation = release_reservation(
        db_session,
        reservation_id=reservation.id,
        qty=Decimal("2.000"),
        actor=actor,
    )
    db_session.commit()
    balance = db_session.get(StockBalance, (product.id, warehouse.id))
    assert balance is not None
    assert balance.qty_on_hand == Decimal("10.000")
    assert balance.qty_reserved == Decimal("4.000")
    assert line.qty_reserved == Decimal("4.000")
    assert reservation.status == "ACTIVE"
    assert reservation.qty_released == Decimal("2.000")

    reservation = release_reservation(
        db_session,
        reservation_id=reservation.id,
        qty=Decimal("4.000"),
        actor=actor,
    )
    db_session.commit()
    assert reservation.status == "RELEASED"
    assert reservation.qty_released == Decimal("6.000")
    assert balance.qty_reserved == Decimal("0.000")
    assert balance.qty_on_hand == Decimal("10.000")
    assert line.qty_reserved == Decimal("0.000")


def test_partial_consume_posts_stock_and_cost_then_completes_reservation(
    db_session: Session,
    reservation_fixture: tuple[User, Product, Warehouse, SalesOrderLine],
) -> None:
    actor, product, warehouse, line = reservation_fixture
    reservation = reserve_stock(
        db_session,
        sales_order_line_id=line.id,
        qty=Decimal("6.000"),
        actor=actor,
    )
    db_session.commit()

    reservation, transaction = consume_reservation(
        db_session,
        reservation_id=reservation.id,
        qty=Decimal("3.000"),
        actor=actor,
    )
    db_session.commit()
    balance = db_session.get(StockBalance, (product.id, warehouse.id))
    assert balance is not None
    assert balance.qty_on_hand == Decimal("7.000")
    assert balance.qty_reserved == Decimal("3.000")
    assert balance.available == Decimal("4.000")
    assert line.qty_reserved == Decimal("3.000")
    assert line.qty_delivered == Decimal("3.000")
    assert reservation.status == "ACTIVE"
    assert reservation.qty_consumed == Decimal("3.000")
    assert transaction.movement_type == MovementType.SALE_DELIVERY
    assert transaction.qty_signed == Decimal("-3.000")
    assert transaction.unit_cost == Decimal("2.5000")
    assert transaction.source_type == "STOCK_RESERVATION"
    assert transaction.source_id == reservation.id
    assert transaction.source_line_id == line.id

    reservation, transaction = consume_reservation(
        db_session,
        reservation_id=reservation.id,
        qty=Decimal("3.000"),
        actor=actor,
    )
    db_session.commit()
    assert reservation.status == "CONSUMED"
    assert reservation.qty_consumed == Decimal("6.000")
    assert balance.qty_on_hand == Decimal("4.000")
    assert balance.qty_reserved == Decimal("0.000")
    assert line.qty_reserved == Decimal("0.000")
    assert line.qty_delivered == Decimal("6.000")
    assert transaction.qty_signed == Decimal("-3.000")
    assert (
        db_session.scalar(
            select(func.sum(StockTransaction.qty_signed)).where(
                StockTransaction.product_id == product.id,
                StockTransaction.warehouse_id == warehouse.id,
            )
        )
        == balance.qty_on_hand
    )


def test_consuming_more_than_remaining_reservation_is_rejected(
    db_session: Session,
    reservation_fixture: tuple[User, Product, Warehouse, SalesOrderLine],
) -> None:
    actor, _, _, line = reservation_fixture
    reservation = reserve_stock(
        db_session,
        sales_order_line_id=line.id,
        qty=Decimal("4.000"),
        actor=actor,
    )
    db_session.commit()

    with pytest.raises(HTTPException) as error:
        consume_reservation(
            db_session,
            reservation_id=reservation.id,
            qty=Decimal("4.001"),
            actor=actor,
        )
    assert error.value.status_code == 409
    assert error.value.detail == "RESERVATION_QUANTITY_EXCEEDED"
