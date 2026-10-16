from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.modules.auth.models import AuditLog, Permission, User
from app.modules.auth.seed import seed_initial_admin
from app.modules.employees.models import Employee


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
    seeded = seed_initial_admin(db)
    db.commit()
    assert seeded.password is not None
    response = client.post(
        "/api/v1/auth/login",
        json={"username": seeded.username, "password": seeded.password},
    )
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def _employee_payload(code: str = "EMP-001") -> dict[str, str]:
    return {
        "code": code,
        "name": "Ayesha Rahman",
        "mobile": "01712345678",
        "email": "ayesha@example.com",
        "designation": "Production supervisor",
        "department": "Production",
        "join_date": "2024-02-01",
        "base_salary": "25000.00",
    }


def test_employee_crud_search_soft_delete_restore_and_audit(
    client: TestClient, db_session: Session
) -> None:
    headers = _login_admin(client, db_session)
    created = client.post("/api/v1/employees", headers=headers, json=_employee_payload())
    assert created.status_code == 201
    employee_id = created.json()["id"]
    assert created.json()["base_salary"] == "25000.00"

    duplicate = client.post(
        "/api/v1/employees", headers=headers, json=_employee_payload("emp-001")
    )
    assert duplicate.status_code == 409

    updated = client.patch(
        f"/api/v1/employees/{employee_id}",
        headers=headers,
        json={"designation": "Operations supervisor", "base_salary": "26000.00"},
    )
    assert updated.status_code == 200
    assert updated.json()["designation"] == "Operations supervisor"

    found = client.get(
        "/api/v1/employees",
        headers=headers,
        params={"search": "ayesha", "limit": 10},
    )
    assert found.status_code == 200
    assert [employee["id"] for employee in found.json()] == [employee_id]

    deleted = client.delete(f"/api/v1/employees/{employee_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["is_active"] is False
    assert client.get("/api/v1/employees", headers=headers).json() == []

    inactive = client.get(
        "/api/v1/employees",
        headers=headers,
        params={"include_inactive": "true"},
    )
    assert inactive.status_code == 200
    assert len(inactive.json()) == 1

    restored = client.post(
        f"/api/v1/employees/{employee_id}/restore", headers=headers
    )
    assert restored.status_code == 200
    assert restored.json()["is_active"] is True

    audit = list(
        db_session.scalars(
            select(AuditLog).where(AuditLog.entity_type == "employee")
        )
    )
    assert [row.action for row in audit].count("CREATE") == 1
    assert [row.action for row in audit].count("UPDATE") == 1
    assert [row.action for row in audit].count("DELETE") == 1
    assert [row.action for row in audit].count("STATUS") == 1
    assert db_session.get(Employee, employee_id) is not None


def test_employee_validation_and_permission_denial(
    client: TestClient, db_session: Session
) -> None:
    headers = _login_admin(client, db_session)
    invalid = client.post(
        "/api/v1/employees",
        headers=headers,
        json={**_employee_payload("EMP-BAD"), "base_salary": "-1.00"},
    )
    assert invalid.status_code == 422
    invalid_mobile = client.post(
        "/api/v1/employees",
        headers=headers,
        json={**_employee_payload("EMP-BAD-MOBILE"), "mobile": "abc"},
    )
    assert invalid_mobile.status_code == 422

    admin = db_session.scalar(select(User).where(User.username == "admin"))
    assert admin is not None
    employee_read = db_session.scalar(
        select(Permission).where(Permission.code == "employees.read")
    )
    assert employee_read is not None
    admin.roles[0].permissions.remove(employee_read)

    user = User(
        username="employee-read-denied",
        full_name="No Employee Access",
        password_hash=hash_password("NoEmployeeAccess-123"),
    )
    db_session.add(user)
    db_session.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"username": user.username, "password": "NoEmployeeAccess-123"},
    )
    assert login.status_code == 200
    no_permission = {"Authorization": "Bearer " + login.json()["access_token"]}
    denied = client.get("/api/v1/employees", headers=no_permission)
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "PERMISSION_DENIED"
