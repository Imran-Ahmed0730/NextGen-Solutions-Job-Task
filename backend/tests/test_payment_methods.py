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


def test_payment_method_crud_soft_delete_and_audit(client: TestClient, db_session: Session) -> None:
    headers = _login_admin(client, db_session)

    cash = client.post(
        "/api/v1/payment-methods",
        headers=headers,
        json={"name": " Cash ", "type": "CASH"},
    )
    assert cash.status_code == 201
    cash_id = cash.json()["id"]
    assert cash.json()["name"] == "Cash"
    assert cash.json()["type"] == "CASH"

    bank = client.post(
        "/api/v1/payment-methods",
        headers=headers,
        json={"name": "Bank Transfer", "type": "BANK"},
    )
    assert bank.status_code == 201

    invalid_type = client.post(
        "/api/v1/payment-methods",
        headers=headers,
        json={"name": "Bad", "type": "CRYPTO"},
    )
    assert invalid_type.status_code == 422

    updated = client.patch(
        f"/api/v1/payment-methods/{cash_id}",
        headers=headers,
        json={"name": "Cash on Hand"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Cash on Hand"

    deleted = client.delete(f"/api/v1/payment-methods/{cash_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["deleted_at"] is not None

    active = client.get("/api/v1/payment-methods", headers=headers).json()
    assert [item["name"] for item in active] == ["Bank Transfer"]

    restored = client.post(f"/api/v1/payment-methods/{cash_id}/activate", headers=headers)
    assert restored.status_code == 200
    assert restored.json()["deleted_at"] is None

    audits = list(
        db_session.scalars(select(AuditLog).where(AuditLog.entity_type == "payment_method"))
    )
    actions = [entry.action for entry in audits]
    assert actions.count("CREATE") == 2
    assert actions.count("UPDATE") == 1
    assert actions.count("DELETE") == 1
    assert actions.count("STATUS") == 1


def test_payment_method_permission_denial(client: TestClient, db_session: Session) -> None:
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

    assert client.get("/api/v1/payment-methods", headers=headers).status_code == 403
    assert (
        client.post(
            "/api/v1/payment-methods", headers=headers, json={"name": "Cash", "type": "CASH"}
        ).status_code
        == 403
    )
    assert (
        client.patch("/api/v1/payment-methods/1", headers=headers, json={"name": "X"}).status_code
        == 403
    )
    assert client.delete("/api/v1/payment-methods/1", headers=headers).status_code == 403
    assert client.post("/api/v1/payment-methods/1/activate", headers=headers).status_code == 403
