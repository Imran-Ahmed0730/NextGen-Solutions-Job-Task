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


def test_company_setting_key_value_crud_audit(
    client: TestClient, db_session: Session
) -> None:
    headers = _login_admin(client, db_session)

    created = client.post(
        "/api/v1/company-settings",
        headers=headers,
        json={"key": "company_name", "value": "Sabuj Pran"},
    )
    assert created.status_code == 201
    assert created.json() == {"key": "company_name", "value": "Sabuj Pran"}

    duplicate = client.post(
        "/api/v1/company-settings",
        headers=headers,
        json={"key": "company_name", "value": "Duplicate"},
    )
    assert duplicate.status_code == 409

    fetched = client.get("/api/v1/company-settings/company_name", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["value"] == "Sabuj Pran"

    updated = client.patch(
        "/api/v1/company-settings/company_name",
        headers=headers,
        json={"value": "Sabuj Pran Ltd"},
    )
    assert updated.status_code == 200
    assert updated.json()["value"] == "Sabuj Pran Ltd"

    listed = client.get("/api/v1/company-settings", headers=headers).json()
    assert any(item["key"] == "company_name" for item in listed)

    deleted = client.delete("/api/v1/company-settings/company_name", headers=headers)
    assert deleted.status_code == 204

    missing = client.get("/api/v1/company-settings/company_name", headers=headers)
    assert missing.status_code == 404

    audits = list(
        db_session.scalars(
            select(AuditLog).where(AuditLog.entity_type == "company_setting")
        )
    )
    actions = [entry.action for entry in audits]
    assert actions == ["CREATE", "UPDATE", "DELETE"]


def test_company_setting_permission_denial(
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

    assert client.get("/api/v1/company-settings", headers=headers).status_code == 403
    assert (
        client.post(
            "/api/v1/company-settings",
            headers=headers,
            json={"key": "company_name", "value": "X"},
        ).status_code
        == 403
    )
    assert (
        client.patch(
            "/api/v1/company-settings/company_name",
            headers=headers,
            json={"value": "Y"},
        ).status_code
        == 403
    )
    assert (
        client.delete("/api/v1/company-settings/company_name", headers=headers).status_code == 403
    )