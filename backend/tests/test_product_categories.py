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
from app.modules.product_categories.models import ProductCategory


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


def test_product_category_crud_hierarchy_restore_and_audit(
    client: TestClient, db_session: Session
) -> None:
    headers = _login_admin(client, db_session)
    parent = client.post(
        "/api/v1/product-categories",
        headers=headers,
        json={"name": "Raw Materials"},
    )
    assert parent.status_code == 201
    parent_id = parent.json()["id"]
    assert parent.json()["parent_id"] is None

    child = client.post(
        "/api/v1/product-categories",
        headers=headers,
        json={"name": "Packaging", "parent_id": parent_id},
    )
    assert child.status_code == 201
    child_id = child.json()["id"]
    assert child.json()["parent_id"] == parent_id

    updated = client.patch(
        f"/api/v1/product-categories/{child_id}",
        headers=headers,
        json={"name": "Packaging Materials"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Packaging Materials"
    assert updated.json()["parent_id"] == parent_id

    deleted = client.delete(f"/api/v1/product-categories/{parent_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["is_active"] is False
    assert deleted.json()["deleted_at"] is not None
    assert [item["name"] for item in client.get(
        "/api/v1/product-categories", headers=headers
    ).json()] == ["Packaging Materials"]

    inactive = client.get(
        "/api/v1/product-categories?include_inactive=true", headers=headers
    )
    assert inactive.status_code == 200
    assert len(inactive.json()) == 2

    restored = client.post(
        f"/api/v1/product-categories/{parent_id}/activate", headers=headers
    )
    assert restored.status_code == 200
    assert restored.json()["is_active"] is True
    assert restored.json()["deleted_at"] is None

    category_audits = list(
        db_session.scalars(
            select(AuditLog).where(AuditLog.entity_type == "product_category")
        )
    )
    assert [entry.action for entry in category_audits].count("CREATE") == 2
    assert [entry.action for entry in category_audits].count("UPDATE") == 1
    assert [entry.action for entry in category_audits].count("DELETE") == 1
    assert [entry.action for entry in category_audits].count("STATUS") == 1
    assert db_session.get(ProductCategory, parent_id) is not None


def test_product_category_rejects_invalid_parent_and_hierarchy_cycle(
    client: TestClient, db_session: Session
) -> None:
    headers = _login_admin(client, db_session)
    missing_parent = client.post(
        "/api/v1/product-categories",
        headers=headers,
        json={"name": "Invalid", "parent_id": 999},
    )
    assert missing_parent.status_code == 422

    root = client.post(
        "/api/v1/product-categories", headers=headers, json={"name": "Root"}
    ).json()
    child = client.post(
        "/api/v1/product-categories",
        headers=headers,
        json={"name": "Child", "parent_id": root["id"]},
    ).json()
    self_parent = client.patch(
        f"/api/v1/product-categories/{root['id']}",
        headers=headers,
        json={"parent_id": root["id"]},
    )
    assert self_parent.status_code == 422

    descendant_parent = client.patch(
        f"/api/v1/product-categories/{root['id']}",
        headers=headers,
        json={"parent_id": child["id"]},
    )
    assert descendant_parent.status_code == 422


def test_update_preserves_reference_to_soft_deleted_parent(
    client: TestClient, db_session: Session
) -> None:
    headers = _login_admin(client, db_session)
    parent = client.post(
        "/api/v1/product-categories", headers=headers, json={"name": "Parent"}
    ).json()
    child = client.post(
        "/api/v1/product-categories",
        headers=headers,
        json={"name": "Child", "parent_id": parent["id"]},
    ).json()
    client.delete(f"/api/v1/product-categories/{parent['id']}", headers=headers)

    updated = client.patch(
        f"/api/v1/product-categories/{child['id']}",
        headers=headers,
        json={"name": "Updated child"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated child"
    assert updated.json()["parent_id"] == parent["id"]


def test_category_can_be_created_inactive_and_status_changes_are_audited(
    client: TestClient, db_session: Session
) -> None:
    headers = _login_admin(client, db_session)
    created = client.post(
        "/api/v1/product-categories",
        headers=headers,
        json={"name": "Temporarily unavailable", "is_active": False},
    )
    assert created.status_code == 201
    assert created.json()["is_active"] is False
    assert created.json()["deleted_at"] is None

    assert client.get("/api/v1/product-categories", headers=headers).json() == []
    all_categories = client.get(
        "/api/v1/product-categories?include_inactive=true", headers=headers
    ).json()
    assert len(all_categories) == 1

    activated = client.patch(
        f"/api/v1/product-categories/{created.json()['id']}",
        headers=headers,
        json={"is_active": True},
    )
    assert activated.status_code == 200
    assert activated.json()["is_active"] is True

    deactivated = client.patch(
        f"/api/v1/product-categories/{created.json()['id']}",
        headers=headers,
        json={"is_active": False},
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    status_audits = list(
        db_session.scalars(
            select(AuditLog).where(
                AuditLog.entity_type == "product_category",
                AuditLog.action == "STATUS",
            )
        )
    )
    assert len(status_audits) == 2


def test_product_category_permission_denial(client: TestClient, db_session: Session) -> None:
    _login_admin(client, db_session)
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

    assert client.get("/api/v1/product-categories", headers=read_only_headers).status_code == 403
    assert (
        client.post(
            "/api/v1/product-categories",
            headers=read_only_headers,
            json={"name": "Denied"},
        ).status_code
        == 403
    )
    assert (
        client.patch(
            "/api/v1/product-categories/1",
            headers=read_only_headers,
            json={"name": "Denied"},
        ).status_code
        == 403
    )
    assert (
        client.delete("/api/v1/product-categories/1", headers=read_only_headers).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/product-categories/1/activate", headers=read_only_headers
        ).status_code
        == 403
    )
