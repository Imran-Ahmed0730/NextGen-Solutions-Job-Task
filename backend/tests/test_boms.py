from collections.abc import Generator

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
from app.modules.boms.models import BOM
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


@pytest.fixture
def bom_fixture(
    db_session: Session,
) -> tuple[User, str, Product, Product, Product]:
    seeded = seed_initial_admin(db_session)
    assert seeded.password is not None
    actor = db_session.scalar(select(User).where(User.username == seeded.username))
    assert actor is not None
    category = ProductCategory(name="Production materials")
    unit = Unit(name="Piece", code="prod-pc", allow_decimal=True)
    db_session.add_all([category, unit])
    db_session.flush()
    raw = Product(
        sku="RAW-BOM-01",
        name="Raw Material",
        type=ProductType.RAW,
        category_id=category.id,
        unit_id=unit.id,
        is_stocked=True,
    )
    second_raw = Product(
        sku="RAW-BOM-02",
        name="Second Raw Material",
        type=ProductType.RAW,
        category_id=category.id,
        unit_id=unit.id,
        is_stocked=True,
    )
    finished = Product(
        sku="FG-BOM-01",
        name="Finished Product",
        type=ProductType.FINISHED,
        category_id=category.id,
        unit_id=unit.id,
        is_stocked=True,
    )
    trading = Product(
        sku="TRADING-BOM-01",
        name="Trading Product",
        type=ProductType.TRADING,
        category_id=category.id,
        unit_id=unit.id,
        is_stocked=True,
    )
    db_session.add_all([raw, second_raw, finished, trading])
    db_session.commit()
    for product in (raw, second_raw, finished, trading):
        db_session.refresh(product)
    return actor, seeded.password, raw, second_raw, finished


def _login(client: TestClient, actor: User, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": actor.username, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def _payload(finished: Product, raw: Product, code: str = "BOM-01") -> dict[str, object]:
    return {
        "code": code,
        "finished_product_id": finished.id,
        "output_qty": "10.000",
        "labor_cost_default": "2.00",
        "overhead_cost_default": "1.50",
        "lines": [{"raw_product_id": raw.id, "qty": "3.250"}],
    }


def test_bom_create_update_soft_delete_restore_and_audit(
    client: TestClient,
    db_session: Session,
    bom_fixture: tuple[User, str, Product, Product, Product],
) -> None:
    actor, password, raw, second_raw, finished = bom_fixture
    headers = _login(client, actor, password)

    options = client.get("/api/v1/production/boms/options", headers=headers)
    assert options.status_code == 200
    assert {product["id"] for product in options.json()["raw_products"]} == {
        raw.id,
        second_raw.id,
    }

    created = client.post(
        "/api/v1/production/boms",
        headers=headers,
        json=_payload(finished, raw),
    )
    assert created.status_code == 201
    bom = created.json()
    assert bom["code"] == "BOM-01"
    assert bom["output_qty"] == "10.000"
    assert bom["labor_cost_default"] == "2.00"
    assert len(bom["lines"]) == 1
    assert bom["lines"][0]["raw_product_id"] == raw.id
    assert bom["lines"][0]["qty"] == "3.250"
    assert db_session.scalar(select(BOM).where(BOM.id == bom["id"])) is not None

    changed = _payload(finished, second_raw, "BOM-02")
    changed["output_qty"] = "5.000"
    updated = client.put(
        f"/api/v1/production/boms/{bom['id']}",
        headers=headers,
        json=changed,
    )
    assert updated.status_code == 200
    assert updated.json()["code"] == "BOM-02"
    assert updated.json()["output_qty"] == "5.000"
    assert updated.json()["lines"][0]["raw_product_id"] == second_raw.id

    deleted = client.delete(f"/api/v1/production/boms/{bom['id']}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["deleted_at"] is not None
    assert client.get("/api/v1/production/boms", headers=headers).json() == []
    restored = client.post(
        f"/api/v1/production/boms/{bom['id']}/activate",
        headers=headers,
    )
    assert restored.status_code == 200
    assert restored.json()["is_active"] is True

    audits = list(
        db_session.scalars(
            select(AuditLog).where(AuditLog.entity_type == "bom").order_by(AuditLog.id)
        )
    )
    assert [audit.action for audit in audits] == ["CREATE", "UPDATE", "DELETE", "STATUS"]


def test_bom_validation_and_permission_denial(
    client: TestClient,
    db_session: Session,
    bom_fixture: tuple[User, str, Product, Product, Product],
) -> None:
    actor, password, raw, _, finished = bom_fixture
    headers = _login(client, actor, password)

    duplicate_components = _payload(finished, raw)
    duplicate_components["lines"] = [
        {"raw_product_id": raw.id, "qty": "1.000"},
        {"raw_product_id": raw.id, "qty": "2.000"},
    ]
    assert (
        client.post(
            "/api/v1/production/boms",
            headers=headers,
            json=duplicate_components,
        ).status_code
        == 422
    )

    invalid_product = _payload(finished, raw)
    invalid_product["finished_product_id"] = raw.id
    assert (
        client.post(
            "/api/v1/production/boms",
            headers=headers,
            json=invalid_product,
        ).status_code
        == 422
    )

    duplicate_code = client.post(
        "/api/v1/production/boms",
        headers=headers,
        json=_payload(finished, raw),
    )
    assert duplicate_code.status_code == 201
    conflict = client.post(
        "/api/v1/production/boms",
        headers=headers,
        json=_payload(finished, raw, "bom-01"),
    )
    assert conflict.status_code == 409

    readonly = User(
        username="bom_readonly",
        full_name="BOM Readonly",
        password_hash=hash_password("ReadOnly-Password-123"),
    )
    db_session.add(readonly)
    db_session.commit()
    readonly_headers = _login(client, readonly, "ReadOnly-Password-123")
    assert client.get("/api/v1/production/boms", headers=readonly_headers).status_code == 403
    assert (
        client.post(
            "/api/v1/production/boms",
            headers=readonly_headers,
            json=_payload(finished, raw),
        ).status_code
        == 403
    )
