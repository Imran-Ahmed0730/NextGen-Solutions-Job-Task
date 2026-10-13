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
from app.modules.products.models import Product, ProductType
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


def _seed_product(db: Session) -> Product:
    unit = Unit(name="Piece", code="PCS", allow_decimal=False)
    category = ProductCategory(name="Finished Goods")
    db.add_all([unit, category])
    db.commit()
    product = Product(
        sku="P1",
        name="Product One",
        type=ProductType.TRADING,
        category_id=category.id,
        unit_id=unit.id,
        is_stocked=True,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def test_price_list_crud_default_dates_product_prices_and_audit(
    client: TestClient, db_session: Session
) -> None:
    headers = _login_admin(client, db_session)
    product = _seed_product(db_session)

    first = client.post(
        "/api/v1/price-lists",
        headers=headers,
        json={
            "name": " Retail ",
            "is_default": True,
            "valid_from": "2026-01-01",
            "valid_to": "2026-12-31",
            "is_active": True,
        },
    )
    assert first.status_code == 201
    first_id = first.json()["id"]
    assert first.json()["name"] == "Retail"
    assert first.json()["is_default"] is True

    second = client.post(
        "/api/v1/price-lists",
        headers=headers,
        json={"name": "Wholesale", "is_default": True},
    )
    assert second.status_code == 201

    first_detail = client.get(f"/api/v1/price-lists/{first_id}", headers=headers).json()
    assert first_detail["is_default"] is False

    updated = client.patch(
        f"/api/v1/price-lists/{first_id}",
        headers=headers,
        json={"name": "Retail Updated", "is_default": True},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Retail Updated"
    assert updated.json()["is_default"] is True

    # Product price
    price = client.post(
        f"/api/v1/price-lists/{first_id}/prices",
        headers=headers,
        json={"product_id": product.id, "price": "10.50"},
    )
    assert price.status_code == 201
    price_id = price.json()["id"]
    assert Decimal(price.json()["price"]) == Decimal("10.50")

    duplicate = client.post(
        f"/api/v1/price-lists/{first_id}/prices",
        headers=headers,
        json={"product_id": product.id, "price": "11.00"},
    )
    assert duplicate.status_code == 409

    patched_price = client.patch(
        f"/api/v1/price-lists/{first_id}/prices/{price_id}",
        headers=headers,
        json={"price": "12.00"},
    )
    assert patched_price.status_code == 200
    assert Decimal(patched_price.json()["price"]) == Decimal("12.00")

    prices = client.get(f"/api/v1/price-lists/{first_id}/prices", headers=headers).json()
    assert len(prices) == 1

    deleted_price = client.delete(
        f"/api/v1/price-lists/{first_id}/prices/{price_id}", headers=headers
    )
    assert deleted_price.status_code == 204
    prices_after = client.get(f"/api/v1/price-lists/{first_id}/prices", headers=headers).json()
    assert prices_after == []

    deleted = client.delete(f"/api/v1/price-lists/{first_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["deleted_at"] is not None

    active = [item["id"] for item in client.get("/api/v1/price-lists", headers=headers).json()]
    assert first_id not in active

    restored = client.post(
        f"/api/v1/price-lists/{first_id}/activate", headers=headers
    )
    assert restored.status_code == 200
    assert restored.json()["deleted_at"] is None

    price_list_audits = list(
        db_session.scalars(select(AuditLog).where(AuditLog.entity_type == "price_list"))
    )
    actions = [entry.action for entry in price_list_audits]
    assert actions.count("CREATE") == 2
    assert actions.count("UPDATE") == 1
    assert actions.count("DELETE") == 1
    assert actions.count("STATUS") == 1

    product_price_audits = list(
        db_session.scalars(
            select(AuditLog).where(AuditLog.entity_type == "product_price")
        )
    )
    price_actions = [entry.action for entry in product_price_audits]
    assert price_actions.count("CREATE") == 1
    assert price_actions.count("UPDATE") == 1
    assert price_actions.count("DELETE") == 1


def test_price_list_permission_denial(
    client: TestClient, db_session: Session
) -> None:
    user = User(
        username="readonly",
        full_name="Read Only",
        password_hash=hash_password("ReadOnly-Password-123"),
    )
    db_session.add(user)
    db_session.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "readonly", "password": "ReadOnly-Password-123"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert client.get("/api/v1/price-lists", headers=headers).status_code == 403
    assert (
        client.post(
            "/api/v1/price-lists",
            headers=headers,
            json={"name": "Retail", "is_default": False, "is_active": True},
        ).status_code
        == 403
    )
    assert (
        client.patch("/api/v1/price-lists/1", headers=headers, json={"name": "X"}).status_code
        == 403
    )
    assert client.delete("/api/v1/price-lists/1", headers=headers).status_code == 403
    assert client.post("/api/v1/price-lists/1/activate", headers=headers).status_code == 403
    assert client.get("/api/v1/price-lists/1/prices", headers=headers).status_code == 403
    assert (
        client.post(
            "/api/v1/price-lists/1/prices", headers=headers, json={"product_id": 1, "price": 1}
        ).status_code
        == 403
    )