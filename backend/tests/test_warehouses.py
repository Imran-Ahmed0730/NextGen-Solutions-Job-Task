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


def test_warehouse_crud_soft_delete_restore_and_audit(
    client: TestClient, db_session: Session
) -> None:
    headers = _login_admin(client, db_session)

    created = client.post(
        "/api/v1/warehouses",
        headers=headers,
        json={"name": " Main Store ", "code": " ms ", "address": " Dhaka ", "is_default": True},
    )
    assert created.status_code == 201
    warehouse_id = created.json()["id"]
    assert created.json()["name"] == "Main Store"
    assert created.json()["code"] == "ms"
    assert created.json()["address"] == "Dhaka"
    assert created.json()["is_default"] is True

    second = client.post(
        "/api/v1/warehouses",
        headers=headers,
        json={"name": "Overflow", "code": "of"},
    )
    assert second.status_code == 201

    duplicate = client.post(
        "/api/v1/warehouses",
        headers=headers,
        json={"name": "Duplicate", "code": "MS"},
    )
    assert duplicate.status_code == 409

    updated = client.patch(
        f"/api/v1/warehouses/{warehouse_id}",
        headers=headers,
        json={"name": "Main Warehouse", "address": None},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Main Warehouse"
    assert updated.json()["address"] is None

    deleted = client.delete(f"/api/v1/warehouses/{warehouse_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["is_active"] is False
    assert deleted.json()["is_default"] is False
    assert deleted.json()["deleted_at"] is not None

    active = client.get("/api/v1/warehouses", headers=headers).json()
    assert [item["code"] for item in active] == ["of"]

    inactive = client.get("/api/v1/warehouses?include_inactive=true", headers=headers)
    assert inactive.status_code == 200
    assert len(inactive.json()) == 2

    restored = client.post(f"/api/v1/warehouses/{warehouse_id}/activate", headers=headers)
    assert restored.status_code == 200
    assert restored.json()["is_active"] is True
    assert restored.json()["is_default"] is False

    audits = list(db_session.scalars(select(AuditLog).where(AuditLog.entity_type == "warehouse")))
    actions = [entry.action for entry in audits]
    assert actions.count("CREATE") == 2
    assert actions.count("UPDATE") == 1
    assert actions.count("DELETE") == 1
    assert actions.count("STATUS") == 1


def test_only_one_default_warehouse(client: TestClient, db_session: Session) -> None:
    headers = _login_admin(client, db_session)

    first = client.post(
        "/api/v1/warehouses",
        headers=headers,
        json={"name": "First", "code": "first", "is_default": True},
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/warehouses",
        headers=headers,
        json={"name": "Second", "code": "second", "is_default": True},
    )
    assert second.status_code == 201

    defaults = [
        w for w in client.get("/api/v1/warehouses", headers=headers).json() if w["is_default"]
    ]
    assert len(defaults) == 1
    assert defaults[0]["code"] == "second"

    # Promoting the first back to default demotes the second
    promoted = client.patch(
        f"/api/v1/warehouses/{first.json()['id']}",
        headers=headers,
        json={"is_default": True},
    )
    assert promoted.status_code == 200
    defaults = [
        w for w in client.get("/api/v1/warehouses", headers=headers).json() if w["is_default"]
    ]
    assert len(defaults) == 1
    assert defaults[0]["code"] == "first"


def test_warehouse_validation_and_permission_denial(
    client: TestClient, db_session: Session
) -> None:
    admin_headers = _login_admin(client, db_session)
    invalid = client.post(
        "/api/v1/warehouses",
        headers=admin_headers,
        json={"name": "   ", "code": "ms"},
    )
    assert invalid.status_code == 422

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
    read_only_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert client.get("/api/v1/warehouses", headers=read_only_headers).status_code == 403
    assert (
        client.post(
            "/api/v1/warehouses",
            headers=read_only_headers,
            json={"name": "Store", "code": "st"},
        ).status_code
        == 403
    )
    assert (
        client.patch(
            "/api/v1/warehouses/1",
            headers=read_only_headers,
            json={"name": "New name"},
        ).status_code
        == 403
    )
    assert client.delete("/api/v1/warehouses/1", headers=read_only_headers).status_code == 403
    assert (
        client.post("/api/v1/warehouses/1/activate", headers=read_only_headers).status_code == 403
    )
