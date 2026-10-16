from collections.abc import Generator
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
from app.modules.boms.models import BOM, BOMLine
from app.modules.document_numbering.models import DocumentSequence
from app.modules.inventory.models import MovementType, StockBalance, StockTransaction
from app.modules.inventory.service import post_stock_movement
from app.modules.product_categories.models import ProductCategory
from app.modules.production_orders.models import ProductionOrder, ProductionOutput
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


@pytest.fixture
def production_fixture(
    db_session: Session,
) -> tuple[User, str, BOM, Warehouse, Product, Product]:
    seeded = seed_initial_admin(db_session)
    assert seeded.password is not None
    actor = db_session.scalar(select(User).where(User.username == seeded.username))
    assert actor is not None
    category = ProductCategory(name="Production order products")
    unit = Unit(name="Piece", code="production-piece", allow_decimal=True)
    warehouse = Warehouse(code="PROD-WH", name="Production Warehouse")
    db_session.add_all([category, unit, warehouse])
    db_session.flush()
    raw = Product(
        sku="PROD-RAW-01",
        name="Production Raw Material",
        type=ProductType.RAW,
        category_id=category.id,
        unit_id=unit.id,
        is_stocked=True,
        avg_cost=Decimal("2.0000"),
    )
    finished = Product(
        sku="PROD-FG-01",
        name="Production Finished Good",
        type=ProductType.FINISHED,
        category_id=category.id,
        unit_id=unit.id,
        is_stocked=True,
        avg_cost=Decimal("4.0000"),
    )
    db_session.add_all([raw, finished])
    db_session.flush()
    bom = BOM(
        code="PROD-BOM-01",
        finished_product_id=finished.id,
        output_qty=Decimal("10.000"),
        labor_cost_default=Decimal("2.00"),
        overhead_cost_default=Decimal("1.50"),
        lines=[BOMLine(raw_product_id=raw.id, qty=Decimal("2.500"))],
    )
    db_session.add_all(
        [
            bom,
            DocumentSequence(
                doc_type="PRODUCTION_ORDER",
                prefix="PO-",
                year=2026,
                last_number=0,
                padding=4,
            ),
        ]
    )
    db_session.commit()
    post_stock_movement(
        db_session,
        product_id=raw.id,
        warehouse_id=warehouse.id,
        movement_type=MovementType.OPENING,
        qty_signed=Decimal("20.000"),
        unit_cost=Decimal("2.0000"),
        actor=actor,
    )
    post_stock_movement(
        db_session,
        product_id=finished.id,
        warehouse_id=warehouse.id,
        movement_type=MovementType.OPENING,
        qty_signed=Decimal("2.000"),
        unit_cost=Decimal("4.0000"),
        actor=actor,
    )
    db_session.commit()
    for record in (bom, warehouse, raw, finished):
        db_session.refresh(record)
    return actor, seeded.password, bom, warehouse, raw, finished


def _login(client: TestClient, actor: User, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": actor.username, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def _create_order(
    client: TestClient, headers: dict[str, str], bom: BOM, warehouse: Warehouse, qty: str = "4.000"
) -> dict[str, object]:
    response = client.post(
        "/api/v1/production/orders",
        headers=headers,
        json={
            "doc_date": "2026-10-16",
            "bom_id": bom.id,
            "planned_qty": qty,
            "warehouse_id": warehouse.id,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_production_posting_consumes_stock_and_updates_cost_atomically(
    client: TestClient,
    db_session: Session,
    production_fixture: tuple[User, str, BOM, Warehouse, Product, Product],
) -> None:
    actor, password, bom, warehouse, raw, finished = production_fixture
    headers = _login(client, actor, password)
    order = _create_order(client, headers, bom, warehouse)
    started = client.post(
        f"/api/v1/production/orders/{order['id']}/start",
        headers=headers,
    )
    assert started.status_code == 200
    assert started.json()["status"] == "IN_PROGRESS"

    completed = client.post(
        f"/api/v1/production/orders/{order['id']}/complete",
        headers=headers,
        json={"actual_qty": "5.000", "labor_cost": "2.00", "overhead_cost": "1.50"},
    )
    assert completed.status_code == 200
    result = completed.json()
    assert result["status"] == "COMPLETED"
    assert result["material_cost"] == "2.50"
    assert result["total_cost"] == "6.00"
    assert result["unit_cost"] == "1.2000"
    assert result["consumption"][0]["qty"] == "1.250"
    assert result["consumption"][0]["unit_cost"] == "2.0000"
    assert result["outputs"][0]["qty"] == "5.000"

    db_session.refresh(raw)
    db_session.refresh(finished)
    raw_balance = db_session.get(StockBalance, (raw.id, warehouse.id))
    finished_balance = db_session.get(StockBalance, (finished.id, warehouse.id))
    assert raw_balance is not None and raw_balance.qty_on_hand == Decimal("18.750")
    assert finished_balance is not None and finished_balance.qty_on_hand == Decimal("7.000")
    assert finished.avg_cost == Decimal("2.0000")
    assert db_session.scalar(
        select(func.count(StockTransaction.id)).where(
            StockTransaction.source_type == "PRODUCTION_ORDER",
            StockTransaction.source_id == order["id"],
        )
    ) == 2
    output = db_session.scalar(
        select(ProductionOutput).where(ProductionOutput.production_order_id == order["id"])
    )
    assert output is not None and output.unit_cost == Decimal("1.2000")
    assert db_session.scalar(
        select(func.count(AuditLog.id)).where(
            AuditLog.entity_type == "production_order",
            AuditLog.entity_id == str(order["id"]),
        )
    ) == 3

    duplicate_post = client.post(
        f"/api/v1/production/orders/{order['id']}/complete",
        headers=headers,
        json={"actual_qty": "5.000", "labor_cost": "2.00", "overhead_cost": "1.50"},
    )
    assert duplicate_post.status_code == 409
    assert db_session.scalar(select(func.count(ProductionOrder.id))) == 1


def test_production_start_rejects_shortage_and_update_is_draft_only(
    client: TestClient,
    db_session: Session,
    production_fixture: tuple[User, str, BOM, Warehouse, Product, Product],
) -> None:
    actor, password, bom, warehouse, _, _ = production_fixture
    headers = _login(client, actor, password)
    order = _create_order(client, headers, bom, warehouse, qty="100.000")
    shortage = client.post(
        f"/api/v1/production/orders/{order['id']}/start",
        headers=headers,
    )
    assert shortage.status_code == 409
    assert shortage.json()["detail"] == "STOCK_INSUFFICIENT"
    still_draft = client.get(
        f"/api/v1/production/orders/{order['id']}",
        headers=headers,
    )
    assert still_draft.json()["status"] == "DRAFT"
    changed = client.put(
        f"/api/v1/production/orders/{order['id']}",
        headers=headers,
        json={
            "doc_date": "2026-10-16",
            "bom_id": bom.id,
            "planned_qty": "3.000",
            "warehouse_id": warehouse.id,
        },
    )
    assert changed.status_code == 200
    assert changed.json()["planned_qty"] == "3.000"


def test_production_order_requires_permission(
    client: TestClient,
    db_session: Session,
    production_fixture: tuple[User, str, BOM, Warehouse, Product, Product],
) -> None:
    _, _, bom, warehouse, _, _ = production_fixture
    readonly = User(
        username="production_readonly",
        full_name="Production Readonly",
        password_hash=hash_password("ReadOnly-Password-123"),
    )
    db_session.add(readonly)
    db_session.commit()
    headers = _login(client, readonly, "ReadOnly-Password-123")
    assert client.get("/api/v1/production/orders", headers=headers).status_code == 403
    assert (
        client.post(
            "/api/v1/production/orders",
            headers=headers,
            json={
                "doc_date": "2026-10-16",
                "bom_id": bom.id,
                "planned_qty": "1.000",
                "warehouse_id": warehouse.id,
            },
        ).status_code
        == 403
    )
