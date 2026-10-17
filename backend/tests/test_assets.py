from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.modules.auth.models import AuditLog, Permission, User
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


@pytest.fixture
def admin(
    db_session: Session,
) -> tuple[User, str]:
    seeded = seed_initial_admin(db_session)
    assert seeded.password is not None
    actor = db_session.scalar(select(User).where(User.username == seeded.username))
    assert actor is not None
    db_session.commit()
    return actor, seeded.password


def _login(client: TestClient, actor: User, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": actor.username, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def _asset_payload(code: str = "AST-001") -> dict[str, str]:
    return {
        "asset_code": code,
        "name": "Office printer",
        "category": "Office equipment",
        "purchase_date": "2025-01-10",
        "purchase_cost": "25000.00",
        "location": "Main office",
        "status": "IN_STORE",
    }


def test_asset_location_maintenance_lifecycle_and_audit(
    client: TestClient,
    db_session: Session,
    admin: tuple[User, str],
) -> None:
    actor, password = admin
    headers = _login(client, actor, password)

    created = client.post("/api/v1/assets", headers=headers, json=_asset_payload())
    assert created.status_code == 201
    asset_id = created.json()["id"]

    assigned = client.post(
        f"/api/v1/assets/{asset_id}/assignments",
        headers=headers,
        json={"location": "Accounts office", "assigned_on": "2025-02-01"},
    )
    assert assigned.status_code == 201
    assignment_id = assigned.json()["assignments"][0]["id"]
    assert assigned.json()["status"] == "IN_USE"

    status_change = client.patch(
        f"/api/v1/assets/{asset_id}",
        headers=headers,
        json={"status": "UNDER_MAINTENANCE"},
    )
    assert status_change.status_code == 409

    duplicate_assignment = client.post(
        f"/api/v1/assets/{asset_id}/assignments",
        headers=headers,
        json={"location": "Sales office", "assigned_on": "2025-02-02"},
    )
    assert duplicate_assignment.status_code == 409

    returned = client.post(
        f"/api/v1/assets/{asset_id}/assignments/{assignment_id}/return",
        headers=headers,
        params={"returned_on": "2025-02-10"},
    )
    assert returned.status_code == 200
    assert returned.json()["assignments"][0]["returned_on"] == "2025-02-10"
    assert returned.json()["status"] == "IN_STORE"

    maintenance = client.post(
        f"/api/v1/assets/{asset_id}/maintenance",
        headers=headers,
        json={
            "maintenance_date": "2025-03-01",
            "description": "Replaced toner cartridge",
            "cost": "1200.00",
            "next_due_date": "2025-09-01",
        },
    )
    assert maintenance.status_code == 201
    assert maintenance.json()["maintenance"][0]["cost"] == "1200.00"

    deleted = client.delete(f"/api/v1/assets/{asset_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["is_active"] is False
    assert client.get("/api/v1/assets", headers=headers).json() == []

    inactive = client.get("/api/v1/assets", headers=headers, params={"include_inactive": "true"})
    assert inactive.status_code == 200
    assert len(inactive.json()) == 1

    restored = client.post(f"/api/v1/assets/{asset_id}/restore", headers=headers)
    assert restored.status_code == 200
    assert restored.json()["is_active"] is True

    audit = list(
        db_session.scalars(
            select(AuditLog).where(
                AuditLog.entity_type.in_(("asset", "asset_assignment", "asset_maintenance"))
            )
        )
    )
    assert {row.action for row in audit} >= {"CREATE", "DELETE", "STATUS"}
    assert len(audit) >= 6


def test_asset_validation_and_permission_denial(
    client: TestClient,
    db_session: Session,
    admin: tuple[User, str],
) -> None:
    actor, password = admin
    permission = db_session.scalar(select(Permission).where(Permission.code == "assets.read"))
    assert permission is not None
    actor.roles[0].permissions.remove(permission)
    db_session.commit()

    headers = _login(client, actor, password)
    forbidden = client.get("/api/v1/assets", headers=headers)
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"]["code"] == "PERMISSION_DENIED"

    actor.roles[0].permissions.append(permission)
    db_session.commit()
    headers = _login(client, actor, password)
    invalid = client.post(
        "/api/v1/assets",
        headers=headers,
        json={**_asset_payload("AST-BAD"), "purchase_cost": "-1.00"},
    )
    assert invalid.status_code == 422


def test_asset_assignment_links_active_employee_and_audits_relationship(
    client: TestClient,
    db_session: Session,
    admin: tuple[User, str],
) -> None:
    actor, password = admin
    headers = _login(client, actor, password)
    employee = client.post(
        "/api/v1/employees",
        headers=headers,
        json={
            "code": "EMP-ASSET-001",
            "name": "Asset Custodian",
            "mobile": "01712345678",
            "join_date": "2025-01-01",
            "base_salary": "30000.00",
        },
    )
    assert employee.status_code == 201
    asset = client.post("/api/v1/assets", headers=headers, json=_asset_payload())
    assert asset.status_code == 201

    assigned = client.post(
        f"/api/v1/assets/{asset.json()['id']}/assignments",
        headers=headers,
        json={
            "location": "Accounts office",
            "assigned_on": "2025-02-01",
            "employee_id": employee.json()["id"],
        },
    )
    assert assigned.status_code == 201
    assignment = assigned.json()["assignments"][0]
    assert assignment["employee_id"] == employee.json()["id"]
    assert assignment["employee"] == {
        "id": employee.json()["id"],
        "code": "EMP-ASSET-001",
        "name": "Asset Custodian",
    }

    audit = db_session.scalar(select(AuditLog).where(AuditLog.entity_type == "asset_assignment"))
    assert audit is not None
    assert audit.after_json is not None
    assert audit.after_json["employee_id"] == employee.json()["id"]


def test_asset_assignment_rejects_inactive_employee(
    client: TestClient,
    admin: tuple[User, str],
) -> None:
    actor, password = admin
    headers = _login(client, actor, password)
    employee = client.post(
        "/api/v1/employees",
        headers=headers,
        json={
            "code": "EMP-ASSET-002",
            "name": "Inactive Custodian",
            "mobile": "01712345678",
            "join_date": "2025-01-01",
            "base_salary": "30000.00",
        },
    )
    assert employee.status_code == 201
    assert (
        client.delete(f"/api/v1/employees/{employee.json()['id']}", headers=headers).status_code
        == 200
    )
    asset = client.post("/api/v1/assets", headers=headers, json=_asset_payload())
    assert asset.status_code == 201

    assignment = client.post(
        f"/api/v1/assets/{asset.json()['id']}/assignments",
        headers=headers,
        json={
            "location": "Accounts office",
            "assigned_on": "2025-02-01",
            "employee_id": employee.json()["id"],
        },
    )
    assert assignment.status_code == 422
