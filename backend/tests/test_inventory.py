from collections.abc import Generator
from decimal import Decimal

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.modules.auth.models import AuditLog, User
from app.modules.auth.seed import seed_initial_admin
from app.modules.inventory.models import MovementType, StockBalance, StockTransaction
from app.modules.inventory.service import post_stock_movement, weighted_average_cost
from app.modules.product_categories.models import ProductCategory
from app.modules.products.models import Product, ProductType
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
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def _create_inventory_records(
    db: Session, *, is_stocked: bool = True, allow_decimal: bool = True
) -> tuple[User, str, Product, Warehouse]:
    admin_result = seed_initial_admin(db)
    assert admin_result.password is not None
    admin = db.scalar(select(User).where(User.username == admin_result.username))
    assert admin is not None
    category = ProductCategory(name="Raw Materials")
    unit = Unit(name="Kilogram", code="kg", allow_decimal=allow_decimal)
    warehouse = Warehouse(name="Main Warehouse", code="MAIN")
    db.add_all([category, unit, warehouse])
    db.flush()
    product = Product(
        sku="RAW-001",
        name="Raw Material",
        type=ProductType.RAW,
        category_id=category.id,
        unit_id=unit.id,
        is_stocked=is_stocked,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    db.refresh(warehouse)
    return admin, admin_result.password, product, warehouse


def _post(
    db: Session,
    actor: User,
    product: Product,
    warehouse: Warehouse,
    movement_type: MovementType,
    qty_signed: Decimal,
    *,
    unit_cost: Decimal | None = Decimal("2.0000"),
) -> StockTransaction:
    return post_stock_movement(
        db,
        product_id=product.id,
        warehouse_id=warehouse.id,
        movement_type=movement_type,
        qty_signed=qty_signed,
        unit_cost=unit_cost,
        source_type="TEST",
        source_id=1,
        source_line_id=1,
        actor=actor,
    )


def test_stock_posting_updates_append_only_ledger_and_balance(db_session: Session) -> None:
    actor, _, product, warehouse = _create_inventory_records(db_session)

    receipt = _post(
        db_session,
        actor,
        product,
        warehouse,
        MovementType.OPENING,
        Decimal("12.500"),
    )
    issue = _post(
        db_session,
        actor,
        product,
        warehouse,
        MovementType.PRODUCTION_CONSUME,
        Decimal("-2.250"),
    )
    db_session.commit()

    balance = db_session.get(StockBalance, (product.id, warehouse.id))
    assert balance is not None
    assert balance.qty_on_hand == Decimal("10.250")
    assert balance.qty_reserved == Decimal("0.000")
    assert receipt.id != issue.id
    assert (
        db_session.scalar(
            select(func.sum(StockTransaction.qty_signed)).where(
                StockTransaction.product_id == product.id,
                StockTransaction.warehouse_id == warehouse.id,
            )
        )
        == balance.qty_on_hand
    )
    assert (
        db_session.scalar(
            select(func.count(AuditLog.id)).where(
                AuditLog.entity_type == "stock_transaction"
            )
        )
        == 2
    )


def test_stocked_product_cannot_become_negative_or_consume_reserved_stock(
    db_session: Session,
) -> None:
    actor, _, product, warehouse = _create_inventory_records(db_session)
    _post(
        db_session,
        actor,
        product,
        warehouse,
        MovementType.OPENING,
        Decimal("5.000"),
    )
    db_session.flush()
    balance = db_session.get(StockBalance, (product.id, warehouse.id))
    assert balance is not None
    balance.qty_reserved = Decimal("2.000")
    db_session.flush()

    with pytest.raises(HTTPException) as negative_error:
        _post(
            db_session,
            actor,
            product,
            warehouse,
            MovementType.SALE_DELIVERY,
            Decimal("-6.000"),
        )
    assert negative_error.value.status_code == 409
    assert negative_error.value.detail == "STOCK_INSUFFICIENT"

    with pytest.raises(HTTPException) as reserved_error:
        _post(
            db_session,
            actor,
            product,
            warehouse,
            MovementType.SALE_DELIVERY,
            Decimal("-4.000"),
        )
    assert reserved_error.value.detail == "STOCK_INSUFFICIENT"


def test_non_stocked_product_can_post_negative_quantity(db_session: Session) -> None:
    actor, _, product, warehouse = _create_inventory_records(db_session, is_stocked=False)

    _post(
        db_session,
        actor,
        product,
        warehouse,
        MovementType.SALE_DELIVERY,
        Decimal("-3.000"),
    )
    db_session.commit()

    balance = db_session.get(StockBalance, (product.id, warehouse.id))
    assert balance is not None
    assert balance.qty_on_hand == Decimal("-3.000")


@pytest.mark.parametrize(
    ("movement_type", "qty_signed"),
    [
        (MovementType.PURCHASE_RECEIPT, Decimal("-1.000")),
        (MovementType.SALE_DELIVERY, Decimal("1.000")),
        (MovementType.COUNT_ADJUSTMENT, Decimal("0.000")),
    ],
)
def test_stock_movement_rejects_invalid_quantity_signs(
    db_session: Session, movement_type: MovementType, qty_signed: Decimal
) -> None:
    actor, _, product, warehouse = _create_inventory_records(db_session)

    with pytest.raises(HTTPException) as error:
        _post(db_session, actor, product, warehouse, movement_type, qty_signed)
    assert error.value.status_code == 422


def test_stock_posting_rejects_fractional_quantity_for_whole_unit(db_session: Session) -> None:
    actor, _, product, warehouse = _create_inventory_records(
        db_session, allow_decimal=False
    )

    with pytest.raises(HTTPException) as error:
        _post(
            db_session,
            actor,
            product,
            warehouse,
            MovementType.OPENING,
            Decimal("1.500"),
        )
    assert error.value.status_code == 422


def test_stock_posting_can_be_rolled_back_as_part_of_callers_transaction(
    db_session: Session,
) -> None:
    actor, _, product, warehouse = _create_inventory_records(db_session)

    _post(
        db_session,
        actor,
        product,
        warehouse,
        MovementType.OPENING,
        Decimal("1.000"),
    )
    db_session.rollback()

    assert db_session.get(StockBalance, (product.id, warehouse.id)) is None
    assert db_session.scalar(select(func.count(StockTransaction.id))) == 0
    assert (
        db_session.scalar(
            select(func.count(AuditLog.id)).where(
                AuditLog.entity_type == "stock_transaction"
            )
        )
        == 0
    )


def test_weighted_average_cost_calculator() -> None:
    assert weighted_average_cost(
        old_qty=Decimal("10.000"),
        old_avg_cost=Decimal("2.0000"),
        received_qty=Decimal("5.000"),
        unit_cost=Decimal("5.0000"),
    ) == Decimal("3.0000")


def test_stock_read_endpoints_require_inventory_permission(
    client: TestClient, db_session: Session
) -> None:
    actor, password, product, warehouse = _create_inventory_records(db_session)
    _post(
        db_session,
        actor,
        product,
        warehouse,
        MovementType.OPENING,
        Decimal("4.000"),
    )
    db_session.commit()

    assert client.get("/api/v1/inventory/stock").status_code == 401
    login = client.post(
        "/api/v1/auth/login",
        json={"username": actor.username, "password": password},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    stock = client.get("/api/v1/inventory/stock", headers=headers)
    ledger = client.get(
        f"/api/v1/inventory/ledger?product_id={product.id}&warehouse_id={warehouse.id}",
        headers=headers,
    )
    assert stock.status_code == 200
    assert stock.json()[0]["available"] == "4.000"
    assert ledger.status_code == 200
    assert len(ledger.json()) == 1

    readonly = User(
        username="inventory_readonly",
        full_name="Read Only",
        password_hash=hash_password("ReadOnly-Password-123"),
    )
    db_session.add(readonly)
    db_session.commit()
    readonly_login = client.post(
        "/api/v1/auth/login",
        json={"username": readonly.username, "password": "ReadOnly-Password-123"},
    )
    assert readonly_login.status_code == 200
    readonly_headers = {
        "Authorization": f"Bearer {readonly_login.json()['access_token']}"
    }
    assert client.get("/api/v1/inventory/stock", headers=readonly_headers).status_code == 403
