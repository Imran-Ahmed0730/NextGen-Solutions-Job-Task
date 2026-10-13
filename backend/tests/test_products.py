from collections.abc import Generator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.modules.auth.models import AuditLog, User
from app.modules.auth.seed import seed_initial_admin
from app.modules.product_categories.models import ProductCategory
from app.modules.units.models import Unit


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


def _login_admin(client: TestClient, db: Session) -> dict[str, str]:
    result = seed_initial_admin(db)
    db.commit()
    assert result.password is not None
    response = client.post(
        "/api/v1/auth/login",
        json={"username": result.username, "password": result.password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _seed_category_and_unit(db: Session) -> tuple[ProductCategory, Unit]:
    category = ProductCategory(name="Raw Materials", is_active=True)
    unit = Unit(name="Kilogram", code="kg", allow_decimal=True, is_active=True)
    db.add(category)
    db.add(unit)
    db.commit()
    db.refresh(category)
    db.refresh(unit)
    return category, unit


def test_product_crud_soft_delete_restore_and_audit(
    client: TestClient, db_session: Session
) -> None:
    headers = _login_admin(client, db_session)
    category, unit = _seed_category_and_unit(db_session)

    # 1. Create product
    created = client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "sku": "RAW-WHEAT-01",
            "name": "Wheat Grain",
            "type": "RAW",
            "category_id": category.id,
            "unit_id": unit.id,
            "is_stocked": True,
            "reorder_level": "50.500",
            "sales_price_default": "45.00",
            "description": "High quality wheat",
        },
    )
    assert created.status_code == 201
    prod_data = created.json()
    product_id = prod_data["id"]
    assert prod_data["sku"] == "RAW-WHEAT-01"
    assert prod_data["name"] == "Wheat Grain"
    assert prod_data["type"] == "RAW"
    assert prod_data["category_id"] == category.id
    assert prod_data["category_name"] == "Raw Materials"
    assert prod_data["unit_id"] == unit.id
    assert prod_data["unit_code"] == "kg"
    assert prod_data["unit_name"] == "Kilogram"
    assert Decimal(prod_data["reorder_level"]) == Decimal("50.500")
    assert Decimal(prod_data["avg_cost"]) == Decimal("0.0000")
    assert Decimal(prod_data["sales_price_default"]) == Decimal("45.00")
    assert prod_data["is_active"] is True
    assert prod_data["deleted_at"] is None

    # 2. Get product
    fetched = client.get(f"/api/v1/products/{product_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == product_id

    # 3. Update product
    updated = client.patch(
        f"/api/v1/products/{product_id}",
        headers=headers,
        json={
            "name": "Wheat Grain Grade A",
            "sales_price_default": "48.50",
            "reorder_level": "60.000",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Wheat Grain Grade A"
    assert Decimal(updated.json()["sales_price_default"]) == Decimal("48.50")

    # 4. Delete product (soft delete)
    deleted = client.delete(f"/api/v1/products/{product_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["is_active"] is False
    assert deleted.json()["deleted_at"] is not None

    # Default list excludes deleted products
    active_list = client.get("/api/v1/products", headers=headers)
    assert active_list.status_code == 200
    assert len(active_list.json()) == 0

    # Include inactive includes soft deleted
    all_list = client.get("/api/v1/products?include_inactive=true", headers=headers)
    assert all_list.status_code == 200
    assert len(all_list.json()) == 1

    # 5. Restore product
    restored = client.post(f"/api/v1/products/{product_id}/activate", headers=headers)
    assert restored.status_code == 200
    assert restored.json()["is_active"] is True
    assert restored.json()["deleted_at"] is None

    # 6. Verify audit logs
    audits = list(db_session.scalars(select(AuditLog).where(AuditLog.entity_type == "product")))
    actions = [entry.action for entry in audits]
    assert actions.count("CREATE") == 1
    assert actions.count("UPDATE") == 1
    assert actions.count("DELETE") == 1
    assert actions.count("STATUS") == 1


def test_product_sku_uniqueness(client: TestClient, db_session: Session) -> None:
    headers = _login_admin(client, db_session)
    category, unit = _seed_category_and_unit(db_session)

    res1 = client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "sku": "UNIQUE-SKU",
            "name": "Item 1",
            "type": "TRADING",
            "category_id": category.id,
            "unit_id": unit.id,
        },
    )
    assert res1.status_code == 201

    # Same SKU (case-insensitive) should fail with 409
    res2 = client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "sku": "unique-sku",
            "name": "Item 2",
            "type": "TRADING",
            "category_id": category.id,
            "unit_id": unit.id,
        },
    )
    assert res2.status_code == 409
    assert "sku is already in use" in res2.json()["detail"].lower()


def test_product_validates_category_and_unit(client: TestClient, db_session: Session) -> None:
    headers = _login_admin(client, db_session)
    category, unit = _seed_category_and_unit(db_session)

    # Inactive category
    inactive_cat = ProductCategory(name="Old Category", is_active=False)
    db_session.add(inactive_cat)
    db_session.commit()
    db_session.refresh(inactive_cat)

    res = client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "sku": "TEST-SKU-1",
            "name": "Item",
            "type": "RAW",
            "category_id": inactive_cat.id,
            "unit_id": unit.id,
        },
    )
    assert res.status_code == 400
    assert "category" in res.json()["detail"].lower()

    # Non-existent unit
    res = client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "sku": "TEST-SKU-2",
            "name": "Item",
            "type": "RAW",
            "category_id": category.id,
            "unit_id": 99999,
        },
    )
    assert res.status_code == 400
    assert "unit" in res.json()["detail"].lower()


def test_product_search_and_filters(client: TestClient, db_session: Session) -> None:
    headers = _login_admin(client, db_session)
    category, unit = _seed_category_and_unit(db_session)
    other_cat = ProductCategory(name="Finished Goods", is_active=True)
    db_session.add(other_cat)
    db_session.commit()
    db_session.refresh(other_cat)

    client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "sku": "RAW-OIL",
            "name": "Mustard Oil Raw",
            "type": "RAW",
            "category_id": category.id,
            "unit_id": unit.id,
        },
    )
    client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "sku": "FG-BOTTLE",
            "name": "Mustard Oil Bottle 1L",
            "type": "FINISHED",
            "category_id": other_cat.id,
            "unit_id": unit.id,
        },
    )

    # Search by text
    res = client.get("/api/v1/products?search=bottle", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["sku"] == "FG-BOTTLE"

    # Filter by category
    res = client.get(f"/api/v1/products?category_id={category.id}", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["sku"] == "RAW-OIL"

    # Filter by type
    res = client.get("/api/v1/products?product_type=FINISHED", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["sku"] == "FG-BOTTLE"


def test_product_permissions(client: TestClient, db_session: Session) -> None:
    user = User(
        username="unauthorized-user",
        full_name="Unauthorized User",
        password_hash=hash_password("User-Pass-123"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"username": "unauthorized-user", "password": "User-Pass-123"},
    ).json()
    user_headers = {"Authorization": f"Bearer {login['access_token']}"}

    assert client.get("/api/v1/products", headers=user_headers).status_code == 403
    assert client.post("/api/v1/products", headers=user_headers, json={}).status_code == 403
    assert client.get("/api/v1/products/1", headers=user_headers).status_code == 403
    assert client.patch("/api/v1/products/1", headers=user_headers, json={}).status_code == 403
    assert client.delete("/api/v1/products/1", headers=user_headers).status_code == 403
