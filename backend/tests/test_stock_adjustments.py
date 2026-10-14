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
from app.modules.document_numbering.models import DocumentSequence
from app.modules.inventory.models import MovementType, StockBalance, StockTransaction
from app.modules.inventory.service import post_stock_movement
from app.modules.product_categories.models import ProductCategory
from app.modules.products.models import Product, ProductType
from app.modules.stock_adjustments.models import StockAdjustment
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
def adjustment_fixture(
    db_session: Session,
) -> tuple[User, str, list[Product], Warehouse]:
    result = seed_initial_admin(db_session)
    assert result.password is not None
    actor = db_session.scalar(select(User).where(User.username == result.username))
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
            doc_type="STOCK_ADJUSTMENT",
            prefix="ADJ-",
            year=2026,
            last_number=0,
            padding=4,
        )
    )
    db_session.commit()
    for record in [warehouse, *products]:
        db_session.refresh(record)
    return actor, result.password, products, warehouse


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


def test_adjustment_posts_signed_lines_and_audits_atomically(
    client: TestClient,
    db_session: Session,
    adjustment_fixture: tuple[User, str, list[Product], Warehouse],
) -> None:
    actor, password, products, warehouse = adjustment_fixture
    _post_opening(db_session, actor, products[0], warehouse, Decimal("5.000"))
    _post_opening(db_session, actor, products[1], warehouse, Decimal("5.000"))
    headers = _login(client, actor.username, password)

    response = client.post(
        "/api/v1/inventory/adjustments",
        headers=headers,
        json={
            "doc_date": "2026-10-14",
            "warehouse_id": warehouse.id,
            "reason": "Physical review",
            "lines": [
                {"product_id": products[0].id, "qty_signed": "2.500"},
                {"product_id": products[1].id, "qty_signed": "-1.250"},
            ],
        },
    )

    assert response.status_code == 201
    adjustment = response.json()
    assert adjustment["doc_no"] == "ADJ-20260001"
    assert adjustment["status"] == "POSTED"
    assert adjustment["reason"] == "Physical review"
    assert [line["qty_signed"] for line in adjustment["lines"]] == ["2.500", "-1.250"]
    assert [line["unit_cost"] for line in adjustment["lines"]] == ["1.2500", "2.2500"]
    assert db_session.get(StockBalance, (products[0].id, warehouse.id)).qty_on_hand == Decimal(
        "7.500"
    )
    assert db_session.get(StockBalance, (products[1].id, warehouse.id)).qty_on_hand == Decimal(
        "3.750"
    )
    movements = list(
        db_session.scalars(
            select(StockTransaction)
            .where(StockTransaction.source_type == "STOCK_ADJUSTMENT")
            .order_by(StockTransaction.id)
        )
    )
    assert [(item.movement_type, item.qty_signed) for item in movements] == [
        (MovementType.ADJUSTMENT_IN, Decimal("2.500")),
        (MovementType.ADJUSTMENT_OUT, Decimal("-1.250")),
    ]
    assert all(item.source_id == adjustment["id"] for item in movements)
    assert (
        db_session.scalar(
            select(func.count(AuditLog.id)).where(AuditLog.entity_type == "stock_adjustment")
        )
        == 1
    )

    listed = client.get("/api/v1/inventory/adjustments", headers=headers)
    options = client.get("/api/v1/inventory/adjustments/options", headers=headers)
    detail = client.get(f"/api/v1/inventory/adjustments/{adjustment['id']}", headers=headers)
    assert listed.status_code == 200
    assert listed.json()[0]["doc_no"] == "ADJ-20260001"
    assert options.status_code == 200
    assert options.json()["products"][0]["sku"] == products[0].sku
    assert detail.status_code == 200
    assert detail.json()["id"] == adjustment["id"]


def test_insufficient_adjustment_rolls_back_document_sequence_and_postings(
    client: TestClient,
    db_session: Session,
    adjustment_fixture: tuple[User, str, list[Product], Warehouse],
) -> None:
    actor, password, products, warehouse = adjustment_fixture
    _post_opening(db_session, actor, products[0], warehouse, Decimal("1.000"))
    headers = _login(client, actor.username, password)

    response = client.post(
        "/api/v1/inventory/adjustments",
        headers=headers,
        json={
            "doc_date": "2026-10-14",
            "warehouse_id": warehouse.id,
            "reason": "Damage",
            "lines": [{"product_id": products[0].id, "qty_signed": "-2.000"}],
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "STOCK_INSUFFICIENT"
    assert db_session.scalar(select(func.count(StockAdjustment.id))) == 0
    assert (
        db_session.scalar(
            select(func.count(StockTransaction.id)).where(
                StockTransaction.source_type == "STOCK_ADJUSTMENT"
            )
        )
        == 0
    )
    sequence = db_session.scalar(
        select(DocumentSequence).where(DocumentSequence.doc_type == "STOCK_ADJUSTMENT")
    )
    assert sequence is not None
    assert sequence.last_number == 0
    assert db_session.get(StockBalance, (products[0].id, warehouse.id)).qty_on_hand == Decimal(
        "1.000"
    )


@pytest.mark.parametrize(
    ("lines", "reason"),
    [
        ([{"product_id": 1, "qty_signed": "0.000"}], "Zero quantity"),
        (
            [
                {"product_id": 1, "qty_signed": "1.000"},
                {"product_id": 1, "qty_signed": "-1.000"},
            ],
            "Duplicate product",
        ),
    ],
)
def test_adjustment_rejects_zero_and_duplicate_lines(
    client: TestClient,
    adjustment_fixture: tuple[User, str, list[Product], Warehouse],
    lines: list[dict[str, object]],
    reason: str,
) -> None:
    actor, password, products, warehouse = adjustment_fixture
    headers = _login(client, actor.username, password)
    normalized_lines = [{**line, "product_id": products[0].id} for line in lines]

    response = client.post(
        "/api/v1/inventory/adjustments",
        headers=headers,
        json={
            "doc_date": "2026-10-14",
            "warehouse_id": warehouse.id,
            "reason": reason,
            "lines": normalized_lines,
        },
    )

    assert response.status_code == 422


def test_adjustment_routes_require_permissions(
    client: TestClient,
    db_session: Session,
) -> None:
    assert client.get("/api/v1/inventory/adjustments").status_code == 401

    readonly = User(
        username="adjustment_readonly",
        full_name="Adjustment Readonly",
        password_hash=hash_password("ReadOnly-Password-123"),
    )
    db_session.add(readonly)
    db_session.commit()
    headers = _login(client, readonly.username, "ReadOnly-Password-123")
    assert client.get("/api/v1/inventory/adjustments", headers=headers).status_code == 403
    assert client.get("/api/v1/inventory/adjustments/options", headers=headers).status_code == 403
    assert (
        client.post(
            "/api/v1/inventory/adjustments",
            headers=headers,
            json={
                "doc_date": "2026-10-14",
                "warehouse_id": 1,
                "reason": "Unauthorized adjustment",
                "lines": [{"product_id": 1, "qty_signed": "1.000"}],
            },
        ).status_code
        == 403
    )


def test_adjustment_options_exclude_non_stocked_products(
    client: TestClient,
    db_session: Session,
    adjustment_fixture: tuple[User, str, list[Product], Warehouse],
) -> None:
    actor, password, products, _ = adjustment_fixture
    non_stocked = Product(
        sku="TRD-001",
        name="Non-stocked Product",
        type=ProductType.TRADING,
        category_id=products[0].category_id,
        unit_id=products[0].unit_id,
        is_stocked=False,
    )
    db_session.add(non_stocked)
    db_session.commit()
    headers = _login(client, actor.username, password)

    response = client.get("/api/v1/inventory/adjustments/options", headers=headers)

    assert response.status_code == 200
    assert {item["sku"] for item in response.json()["products"]} == {
        product.sku for product in products
    }
