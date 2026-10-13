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


def test_unit_crud_soft_delete_restore_and_audit(
    client: TestClient, db_session: Session
) -> None:
    headers = _login_admin(client, db_session)
    created = client.post(
        "/api/v1/units",
        headers=headers,
        json={"name": " Kilogram ", "code": " kg ", "allow_decimal": True},
    )
    assert created.status_code == 201
    unit_id = created.json()["id"]
    assert created.json()["name"] == "Kilogram"
    assert created.json()["code"] == "kg"
    assert created.json()["allow_decimal"] is True

    second = client.post(
        "/api/v1/units",
        headers=headers,
        json={"name": "Piece", "code": "pc", "allow_decimal": False},
    )
    assert second.status_code == 201

    duplicate = client.post(
        "/api/v1/units",
        headers=headers,
        json={"name": "Duplicate", "code": "KG", "allow_decimal": False},
    )
    assert duplicate.status_code == 409
    duplicate_update = client.patch(
        f"/api/v1/units/{unit_id}",
        headers=headers,
        json={"code": "PC"},
    )
    assert duplicate_update.status_code == 409
    assert db_session.get(Unit, unit_id).code == "kg"

    updated = client.patch(
        f"/api/v1/units/{unit_id}",
        headers=headers,
        json={"name": "Kilograms", "allow_decimal": False},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Kilograms"
    assert updated.json()["allow_decimal"] is False

    deleted = client.delete(f"/api/v1/units/{unit_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["is_active"] is False
    assert deleted.json()["deleted_at"] is not None
    active_units = client.get("/api/v1/units", headers=headers).json()
    assert [item["code"] for item in active_units] == ["pc"]
    inactive = client.get("/api/v1/units?include_inactive=true", headers=headers)
    assert inactive.status_code == 200
    assert len(inactive.json()) == 2

    restored = client.post(f"/api/v1/units/{unit_id}/activate", headers=headers)
    assert restored.status_code == 200
    assert restored.json()["is_active"] is True
    assert restored.json()["deleted_at"] is None
    assert len(client.get("/api/v1/units", headers=headers).json()) == 2

    unit_audits = list(
        db_session.scalars(select(AuditLog).where(AuditLog.entity_type == "unit"))
    )
    actions = [entry.action for entry in unit_audits]
    assert actions.count("CREATE") == 2
    assert actions.count("UPDATE") == 1
    assert actions.count("DELETE") == 1
    assert actions.count("STATUS") == 1
    assert db_session.get(Unit, unit_id) is not None


def test_unit_validation_and_permission_denial(
    client: TestClient, db_session: Session
) -> None:
    admin_headers = _login_admin(client, db_session)
    invalid = client.post(
        "/api/v1/units",
        headers=admin_headers,
        json={"name": "   ", "code": "kg", "allow_decimal": False},
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

    assert client.get("/api/v1/units", headers=read_only_headers).status_code == 403
    assert (
        client.post(
            "/api/v1/units",
            headers=read_only_headers,
            json={"name": "Piece", "code": "pc", "allow_decimal": False},
        ).status_code
        == 403
    )
    assert (
        client.patch(
            "/api/v1/units/1",
            headers=read_only_headers,
            json={"name": "New name"},
        ).status_code
        == 403
    )
    assert client.delete("/api/v1/units/1", headers=read_only_headers).status_code == 403
    assert (
        client.post("/api/v1/units/1/activate", headers=read_only_headers).status_code == 403
    )
