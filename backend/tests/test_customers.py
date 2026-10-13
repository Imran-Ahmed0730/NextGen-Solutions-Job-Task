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
from app.modules.price_lists.models import PriceList


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        yield session
    engine.dispose()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def _login_admin(client, db):
    result = seed_initial_admin(db)
    db.commit()
    assert result.password is not None
    response = client.post(
        "/api/v1/auth/login",
        json={"username": result.username, "password": result.password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _seed_price_list(db: Session) -> PriceList:
    price_list = PriceList(name="Retail", is_default=True)
    db.add(price_list)
    db.commit()
    db.refresh(price_list)
    return price_list


def test_customer_crud_contacts_statement_and_audit(client, db_session):
    headers = _login_admin(client, db_session)
    price_list = _seed_price_list(db_session)

    created = client.post(
        "/api/v1/customers",
        headers=headers,
        json={
            "code": " CUST-1 ",
            "name": " Acme Customer ",
            "mobile": "01700000000",
            "email": "acme@example.com",
            "address": "Dhaka",
            "credit_limit": "1000.00",
            "opening_due": "250.00",
            "price_list_id": price_list.id,
            "is_active": True,
        },
    )
    assert created.status_code == 201
    customer_id = created.json()["id"]
    assert created.json()["code"] == "CUST-1"
    assert created.json()["name"] == "Acme Customer"

    contact = client.post(
        f"/api/v1/customers/{customer_id}/contacts",
        headers=headers,
        json={"name": "John", "phone": "017", "email": "john@example.com", "designation": "Buyer"},
    )
    assert contact.status_code == 201
    contact_id = contact.json()["id"]

    contact_update = client.patch(
        f"/api/v1/customers/{customer_id}/contacts/{contact_id}",
        headers=headers,
        json={"phone": "018"},
    )
    assert contact_update.status_code == 200
    assert contact_update.json()["phone"] == "018"

    updated = client.patch(
        f"/api/v1/customers/{customer_id}",
        headers=headers,
        json={"name": "Acme Updated", "price_list_id": None, "is_active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Acme Updated"
    assert updated.json()["is_active"] is False

    statement = client.get(f"/api/v1/customers/{customer_id}/statement", headers=headers)
    assert statement.status_code == 200
    assert statement.json()["balance"] == "250.00"

    contacts = client.get(f"/api/v1/customers/{customer_id}/contacts", headers=headers).json()
    assert len(contacts) == 1

    deleted_contact = client.delete(
        f"/api/v1/customers/{customer_id}/contacts/{contact_id}", headers=headers
    )
    assert deleted_contact.status_code == 204

    deleted = client.delete(f"/api/v1/customers/{customer_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["deleted_at"] is not None

    restored = client.post(f"/api/v1/customers/{customer_id}/activate", headers=headers)
    assert restored.status_code == 200
    assert restored.json()["deleted_at"] is None

    audits = list(db_session.scalars(select(AuditLog).where(AuditLog.entity_type == "customer")))
    assert [a.action for a in audits].count("CREATE") == 1
    assert [a.action for a in audits].count("DELETE") == 1
    assert [a.action for a in audits].count("STATUS") == 1

    contact_audits = list(
        db_session.scalars(select(AuditLog).where(AuditLog.entity_type == "customer_contact"))
    )
    assert [a.action for a in contact_audits].count("CREATE") == 1
    assert [a.action for a in contact_audits].count("UPDATE") == 1
    assert [a.action for a in contact_audits].count("DELETE") == 1


def test_customer_permission_denial(client, db_session):
    user = User(
        username="readonly",
        full_name="Read Only",
        password_hash=hash_password("ReadOnly-Password-123"),
    )
    db_session.add(user)
    db_session.commit()
    login = client.post(
        "/api/v1/auth/login", json={"username": "readonly", "password": "ReadOnly-Password-123"}
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert client.get("/api/v1/customers", headers=headers).status_code == 403
    assert (
        client.post(
            "/api/v1/customers", headers=headers, json={"code": "C", "name": "N"}
        ).status_code
        == 403
    )
    assert (
        client.patch("/api/v1/customers/1", headers=headers, json={"name": "X"}).status_code == 403
    )
    assert client.delete("/api/v1/customers/1", headers=headers).status_code == 403
    assert client.post("/api/v1/customers/1/activate", headers=headers).status_code == 403