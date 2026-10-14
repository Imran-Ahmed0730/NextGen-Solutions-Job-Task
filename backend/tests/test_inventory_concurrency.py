import os
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, delete, func, inspect, select
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import sessionmaker

from app.modules.auth.models import AuditLog, User
from app.modules.inventory.models import MovementType, StockBalance, StockTransaction
from app.modules.inventory.service import post_stock_movement
from app.modules.product_categories.models import ProductCategory
from app.modules.products.models import Product, ProductType
from app.modules.units.models import Unit
from app.modules.warehouses.models import Warehouse


@pytest.fixture
def mysql_test_engine() -> Generator[Engine, None, None]:
    database_url = os.environ.get("INVENTORY_CONCURRENCY_DATABASE_URL")
    if not database_url:
        pytest.skip("Set INVENTORY_CONCURRENCY_DATABASE_URL to run the MySQL concurrency test")

    url = make_url(database_url)
    database_name = url.database or ""
    if url.get_backend_name() != "mysql" or not database_name.lower().endswith("_test"):
        pytest.fail(
            "INVENTORY_CONCURRENCY_DATABASE_URL must target a MySQL database ending in '_test'"
        )

    engine = create_engine(url, pool_size=2, max_overflow=0, pool_pre_ping=True)
    required_tables = {
        "audit_logs",
        "product_categories",
        "products",
        "stock_balances",
        "stock_transactions",
        "units",
        "users",
        "warehouses",
    }
    missing_tables = required_tables - set(inspect(engine).get_table_names())
    if missing_tables:
        engine.dispose()
        pytest.fail(
            "Apply project migrations to the dedicated concurrency test database before running "
            "this test"
        )

    yield engine
    engine.dispose()


def test_concurrent_stock_issues_cannot_overdraw_a_stocked_product(
    mysql_test_engine: Engine,
) -> None:
    session_factory = sessionmaker(bind=mysql_test_engine)
    suffix = uuid4().hex
    actor = User(
        username=f"inventory-concurrency-{suffix}",
        full_name="Inventory Concurrency Test",
        password_hash="test-only",
    )
    category = ProductCategory(name=f"Inventory Concurrency {suffix}")
    unit = Unit(name=f"Concurrency Unit {suffix}", code=f"CT{suffix[:10]}", allow_decimal=True)
    warehouse = Warehouse(name=f"Concurrency Warehouse {suffix}", code=f"CW{suffix[:10]}")
    product = Product(
        sku=f"CONC-{suffix}",
        name=f"Concurrency Product {suffix}",
        type=ProductType.RAW,
        category=category,
        unit=unit,
        is_stocked=True,
        avg_cost=Decimal("1.0000"),
    )

    with session_factory() as db:
        db.add_all([actor, category, unit, warehouse, product])
        db.flush()
        actor_id = actor.id
        product_id = product.id
        warehouse_id = warehouse.id
        unit_id = unit.id
        category_id = category.id
        post_stock_movement(
            db,
            product_id=product_id,
            warehouse_id=warehouse_id,
            movement_type=MovementType.OPENING,
            qty_signed=Decimal("10.000"),
            actor=actor,
            source_type="CONCURRENCY_TEST",
            source_id=product_id,
        )
        db.commit()

    barrier = Barrier(2)

    def issue_six_units() -> str:
        with session_factory() as db:
            issue_actor = db.get(User, actor_id)
            assert issue_actor is not None
            barrier.wait(timeout=10)
            try:
                post_stock_movement(
                    db,
                    product_id=product_id,
                    warehouse_id=warehouse_id,
                    movement_type=MovementType.SALE_DELIVERY,
                    qty_signed=Decimal("-6.000"),
                    actor=issue_actor,
                    source_type="CONCURRENCY_TEST",
                    source_id=product_id,
                )
                db.commit()
                return "posted"
            except HTTPException as exc:
                db.rollback()
                return str(exc.detail)

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(issue_six_units) for _ in range(2)]
            outcomes = sorted(future.result(timeout=60) for future in futures)
        assert outcomes == ["STOCK_INSUFFICIENT", "posted"]

        with session_factory() as db:
            balance = db.get(StockBalance, (product_id, warehouse_id))
            ledger_total = db.scalar(
                select(func.sum(StockTransaction.qty_signed)).where(
                    StockTransaction.product_id == product_id,
                    StockTransaction.warehouse_id == warehouse_id,
                )
            )
            assert balance is not None
            assert balance.qty_on_hand == Decimal("4.000")
            assert balance.qty_on_hand == ledger_total
            assert balance.qty_on_hand >= balance.qty_reserved >= Decimal("0.000")
    finally:
        with session_factory.begin() as db:
            transaction_ids = list(
                db.scalars(
                    select(StockTransaction.id).where(
                        StockTransaction.product_id == product_id,
                        StockTransaction.warehouse_id == warehouse_id,
                    )
                )
            )
            if transaction_ids:
                db.execute(
                    delete(AuditLog).where(
                        AuditLog.entity_type == "stock_transaction",
                        AuditLog.entity_id.in_(
                            [str(transaction_id) for transaction_id in transaction_ids]
                        ),
                    )
                )
            db.execute(
                delete(StockTransaction).where(
                    StockTransaction.product_id == product_id,
                    StockTransaction.warehouse_id == warehouse_id,
                )
            )
            db.execute(
                delete(StockBalance).where(
                    StockBalance.product_id == product_id,
                    StockBalance.warehouse_id == warehouse_id,
                )
            )
            db.execute(delete(Product).where(Product.id == product_id))
            db.execute(delete(Warehouse).where(Warehouse.id == warehouse_id))
            db.execute(delete(Unit).where(Unit.id == unit_id))
            db.execute(delete(ProductCategory).where(ProductCategory.id == category_id))
            db.execute(delete(User).where(User.id == actor_id))
