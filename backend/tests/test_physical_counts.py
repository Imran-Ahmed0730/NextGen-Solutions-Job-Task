from collections.abc import Generator
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.modules.auth.models import AuditLog, User
from app.modules.auth.seed import seed_initial_admin
from app.modules.customers.models import Customer
from app.modules.document_numbering.models import DocumentSequence
from app.modules.inventory.models import MovementType, StockBalance, StockTransaction
from app.modules.inventory.service import post_stock_movement, reserve_stock
from app.modules.physical_counts.models import PhysicalCount
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
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def physical_count_fixture(
    db_session: Session,
) -> tuple[User, str, list[Product], Warehouse]:
    seed_result = seed_initial_admin(db_session)
    assert seed_result.password is not None
    actor = db_session.scalar(select(User).where(User.username == seed_result.username))
    assert actor is not None
    category = ProductCategory(name="Raw Materials")
    unit = Unit(name="Kilogram", code="kg", allow_decimal=True)
    warehouse = Warehouse(name="Main Warehouse", code="MAIN")
    db_session.add_all([category, unit, warehouse])
    db_session.flush()
    products = [
        Product(
            sku=f"RAW-00{index}",
            name=f"Raw Material {index}",
            type=ProductType.RAW,
            category_id=category.id,
            unit_id=unit.id,
            is_stocked=True,
            avg_cost=Decimal(f"{index}.2500"),
        )
        for index in range(1, 3)
    ]
    db_session.add_all(products)
    db_session.add(
        DocumentSequence(
            doc_type="PHYSICAL_COUNT",
            prefix="PC-",
            year=2026,
            last_number=0,
            padding=4,
        )
    )
    db_session.commit()
    for record in [warehouse, *products]:
        db_session.refresh(record)
    return actor, seed_result.password, products, warehouse


def _login(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _post_opening(
    db: Session,
    actor: User,
    product: Product,
    warehouse: Warehouse,
    quantity: Decimal,
) -> None:
    post_stock_movement(
        db,
        product_id=product.id,
        warehouse_id=warehouse.id,
        movement_type=MovementType.OPENING,
        qty_signed=quantity,
        actor=actor,
    )
    db.commit()


def _start_count(
    client: TestClient, headers: dict[str, str], warehouse: Warehouse
) -> dict[str, object]:
    response = client.post(
        "/api/v1/inventory/physical-counts",
        headers=headers,
        json={"count_date": "2026-10-14", "warehouse_id": warehouse.id},
    )
    assert response.status_code == 201
    return response.json()


def test_physical_count_snapshots_stock_and_posts_count_variances_atomically(
    client: TestClient,
    db_session: Session,
    physical_count_fixture: tuple[User, str, list[Product], Warehouse],
) -> None:
    actor, password, products, warehouse = physical_count_fixture
    _post_opening(db_session, actor, products[0], warehouse, Decimal("5.000"))
    headers = _login(client, actor.username, password)

    count = _start_count(client, headers, warehouse)
    assert count["doc_no"] is None
    assert count["status"] == "OPEN"
    assert [(line["product_sku"], line["system_qty"]) for line in count["lines"]] == [
        (products[0].sku, "5.000"),
        (products[1].sku, "0.000"),
    ]

    update_url = f"/api/v1/inventory/physical-counts/{count['id']}/lines"
    first_update = client.put(
        update_url,
        headers=headers,
        json={"lines": [{"product_id": products[0].id, "counted_qty": "4.000"}]},
    )
    assert first_update.status_code == 200
    assert first_update.json()["status"] == "OPEN"
    assert first_update.json()["lines"][0]["variance_qty"] == "-1.000"

    second_update = client.put(
        update_url,
        headers=headers,
        json={"lines": [{"product_id": products[1].id, "counted_qty": "0.000"}]},
    )
    assert second_update.status_code == 200
    assert second_update.json()["status"] == "COUNTED"
    assert second_update.json()["lines"][1]["variance_qty"] == "0.000"

    listing = client.get("/api/v1/inventory/physical-counts", headers=headers)
    assert listing.status_code == 200
    assert listing.json()[0]["counted_lines"] == 2

    posted = client.post(
        f"/api/v1/inventory/physical-counts/{count['id']}/post",
        headers=headers,
    )
    assert posted.status_code == 200
    assert posted.json()["doc_no"] == "PC-20260001"
    assert posted.json()["status"] == "POSTED"
    assert db_session.get(StockBalance, (products[0].id, warehouse.id)).qty_on_hand == Decimal(
        "4.000"
    )
    assert db_session.get(StockBalance, (products[1].id, warehouse.id)) is None
    movements = list(
        db_session.scalars(
            select(StockTransaction).where(StockTransaction.source_type == "PHYSICAL_COUNT")
        )
    )
    assert len(movements) == 1
    assert movements[0].product_id == products[0].id
    assert movements[0].movement_type == MovementType.COUNT_ADJUSTMENT
    assert movements[0].qty_signed == Decimal("-1.000")
    assert movements[0].unit_cost == Decimal("1.2500")
    assert movements[0].source_id == count["id"]
    assert (
        db_session.scalar(
            select(func.count(AuditLog.id)).where(AuditLog.entity_type == "physical_count")
        )
        == 4
    )

    repeated_post = client.post(
        f"/api/v1/inventory/physical-counts/{count['id']}/post",
        headers=headers,
    )
    assert repeated_post.status_code == 409
    assert repeated_post.json()["detail"] == "DOCUMENT_POSTED"
    sequence = db_session.scalar(
        select(DocumentSequence).where(DocumentSequence.doc_type == "PHYSICAL_COUNT")
    )
    assert sequence is not None
    assert sequence.last_number == 1


def test_physical_count_rejects_stock_changed_after_snapshot_without_posting(
    client: TestClient,
    db_session: Session,
    physical_count_fixture: tuple[User, str, list[Product], Warehouse],
) -> None:
    actor, password, products, warehouse = physical_count_fixture
    _post_opening(db_session, actor, products[0], warehouse, Decimal("5.000"))
    headers = _login(client, actor.username, password)
    count = _start_count(client, headers, warehouse)

    update = client.put(
        f"/api/v1/inventory/physical-counts/{count['id']}/lines",
        headers=headers,
        json={
            "lines": [
                {"product_id": products[0].id, "counted_qty": "5.000"},
                {"product_id": products[1].id, "counted_qty": "0.000"},
            ]
        },
    )
    assert update.status_code == 200
    _post_opening(db_session, actor, products[0], warehouse, Decimal("1.000"))

    response = client.post(
        f"/api/v1/inventory/physical-counts/{count['id']}/post",
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "PHYSICAL_COUNT_STALE_STOCK"
    stored_count = db_session.get(PhysicalCount, count["id"])
    assert stored_count is not None
    assert stored_count.status == "COUNTED"
    assert stored_count.doc_no is None
    assert (
        db_session.scalar(
            select(func.count(StockTransaction.id)).where(
                StockTransaction.source_type == "PHYSICAL_COUNT"
            )
        )
        == 0
    )
    sequence = db_session.scalar(
        select(DocumentSequence).where(DocumentSequence.doc_type == "PHYSICAL_COUNT")
    )
    assert sequence is not None
    assert sequence.last_number == 0


def test_insufficient_adjustment_rolls_back_entire_physical_count_posting(
    client: TestClient,
    db_session: Session,
    physical_count_fixture: tuple[User, str, list[Product], Warehouse],
) -> None:
    actor, password, products, warehouse = physical_count_fixture
    _post_opening(db_session, actor, products[0], warehouse, Decimal("5.000"))
    _post_opening(db_session, actor, products[1], warehouse, Decimal("5.000"))
    headers = _login(client, actor.username, password)
    count = _start_count(client, headers, warehouse)

    update = client.put(
        f"/api/v1/inventory/physical-counts/{count['id']}/lines",
        headers=headers,
        json={
            "lines": [
                {"product_id": products[0].id, "counted_qty": "6.000"},
                {"product_id": products[1].id, "counted_qty": "2.000"},
            ]
        },
    )
    assert update.status_code == 200

    customer = Customer(code="C-COUNT", name="Count Customer")
    db_session.add(customer)
    db_session.flush()
    order = SalesOrder(
        doc_no="SO-COUNT-001",
        doc_date=date(2026, 10, 14),
        customer_id=customer.id,
        warehouse_id=warehouse.id,
        status="DRAFT",
    )
    db_session.add(order)
    db_session.flush()
    order_line = SalesOrderLine(
        order_id=order.id,
        product_id=products[1].id,
        qty_ordered=Decimal("4.000"),
        unit_price=Decimal("5.00"),
        line_total=Decimal("20.00"),
    )
    db_session.add(order_line)
    db_session.flush()
    reserve_stock(
        db_session,
        sales_order_line_id=order_line.id,
        qty=Decimal("4.000"),
        actor=actor,
    )
    db_session.commit()

    response = client.post(
        f"/api/v1/inventory/physical-counts/{count['id']}/post",
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "STOCK_INSUFFICIENT"
    stored_count = db_session.get(PhysicalCount, count["id"])
    assert stored_count is not None
    assert stored_count.status == "COUNTED"
    assert stored_count.doc_no is None
    assert db_session.get(StockBalance, (products[0].id, warehouse.id)).qty_on_hand == Decimal(
        "5.000"
    )
    second_balance = db_session.get(StockBalance, (products[1].id, warehouse.id))
    assert second_balance is not None
    assert second_balance.qty_on_hand == Decimal("5.000")
    assert second_balance.qty_reserved == Decimal("4.000")
    assert (
        db_session.scalar(
            select(func.count(StockTransaction.id)).where(
                StockTransaction.source_type == "PHYSICAL_COUNT"
            )
        )
        == 0
    )
    sequence = db_session.scalar(
        select(DocumentSequence).where(DocumentSequence.doc_type == "PHYSICAL_COUNT")
    )
    assert sequence is not None
    assert sequence.last_number == 0


def test_physical_count_rejects_invalid_updates_and_requires_permissions(
    client: TestClient,
    db_session: Session,
    physical_count_fixture: tuple[User, str, list[Product], Warehouse],
) -> None:
    actor, password, products, warehouse = physical_count_fixture
    headers = _login(client, actor.username, password)
    count = _start_count(client, headers, warehouse)
    update_url = f"/api/v1/inventory/physical-counts/{count['id']}/lines"

    duplicate = client.put(
        update_url,
        headers=headers,
        json={
            "lines": [
                {"product_id": products[0].id, "counted_qty": "1.000"},
                {"product_id": products[0].id, "counted_qty": "2.000"},
            ]
        },
    )
    negative = client.put(
        update_url,
        headers=headers,
        json={"lines": [{"product_id": products[0].id, "counted_qty": "-1.000"}]},
    )
    excessive_precision = client.put(
        update_url,
        headers=headers,
        json={"lines": [{"product_id": products[0].id, "counted_qty": "1.0001"}]},
    )
    assert duplicate.status_code == 422
    assert negative.status_code == 422
    assert excessive_precision.status_code == 422
    assert client.get("/api/v1/inventory/physical-counts").status_code == 401

    readonly = User(
        username="physical_count_readonly",
        full_name="Physical Count Readonly",
        password_hash=hash_password("ReadOnly-Password-123"),
    )
    db_session.add(readonly)
    db_session.commit()
    readonly_headers = _login(client, readonly.username, "ReadOnly-Password-123")
    assert (
        client.get("/api/v1/inventory/physical-counts", headers=readonly_headers).status_code == 403
    )
    options = client.get("/api/v1/inventory/physical-counts/options", headers=readonly_headers)
    assert options.status_code == 403
    assert (
        client.post(
            "/api/v1/inventory/physical-counts",
            headers=readonly_headers,
            json={"count_date": "2026-10-14", "warehouse_id": warehouse.id},
        ).status_code
        == 403
    )
