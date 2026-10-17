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


def test_income_category_crud_soft_delete_restore_and_audit(
    client: TestClient, db_session: Session
) -> None:
    headers = _login_admin(client, db_session)

    created = client.post(
        "/api/v1/income-categories",
        headers=headers,
        json={"name": " Other Income "},
    )
    assert created.status_code == 201
    category_id = created.json()["id"]
    assert created.json()["name"] == "Other Income"

    invalid = client.post(
        "/api/v1/income-categories",
        headers=headers,
        json={"name": "   "},
    )
    assert invalid.status_code == 422

    updated = client.patch(
        f"/api/v1/income-categories/{category_id}",
        headers=headers,
        json={"name": "Miscellaneous Income"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Miscellaneous Income"

    deleted = client.delete(f"/api/v1/income-categories/{category_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["deleted_at"] is not None

    active = client.get("/api/v1/income-categories", headers=headers).json()
    assert active == []

    restored = client.post(f"/api/v1/income-categories/{category_id}/activate", headers=headers)
    assert restored.status_code == 200
    assert restored.json()["deleted_at"] is None

    audits = list(
        db_session.scalars(select(AuditLog).where(AuditLog.entity_type == "income_category"))
    )
    actions = [entry.action for entry in audits]
    assert actions.count("CREATE") == 1
    assert actions.count("UPDATE") == 1
    assert actions.count("DELETE") == 1
    assert actions.count("STATUS") == 1


def test_income_category_permission_denial(client: TestClient, db_session: Session) -> None:
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

    assert client.get("/api/v1/income-categories", headers=headers).status_code == 403
    assert (
        client.post(
            "/api/v1/income-categories", headers=headers, json={"name": "Income"}
        ).status_code
        == 403
    )
    assert (
        client.patch("/api/v1/income-categories/1", headers=headers, json={"name": "X"}).status_code
        == 403
    )
    assert client.delete("/api/v1/income-categories/1", headers=headers).status_code == 403
    assert client.post("/api/v1/income-categories/1/activate", headers=headers).status_code == 403
