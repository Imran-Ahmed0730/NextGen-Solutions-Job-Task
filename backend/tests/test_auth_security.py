from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.database import Base, get_db
from app.main import app
from app.modules.auth import service
from app.modules.auth.models import AuditLog, Role, User
from app.modules.auth.seed import seed_initial_admin
from app.modules.auth.service import issue_session


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


def _admin(db: Session) -> tuple[User, str]:
    result = seed_initial_admin(db)
    db.commit()
    user = db.scalar(select(User).where(User.username == result.username))
    assert user is not None
    assert result.password is not None
    return user, result.password


def test_user_employee_link_is_validated_and_audited(
    client: TestClient, db_session: Session
) -> None:
    admin, password = _admin(db_session)
    login = client.post(
        "/api/v1/auth/login",
        json={"username": admin.username, "password": password},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    employee = client.post(
        "/api/v1/employees",
        headers=headers,
        json={
            "code": "EMP-USER-LINK",
            "name": "Linked Employee",
            "mobile": "01712345678",
            "join_date": "2025-01-01",
            "base_salary": "30000.00",
        },
    )
    assert employee.status_code == 201

    created = client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={
            "username": "linked-user",
            "full_name": "Linked User",
            "password": "Staff-Password-123",
            "employee_id": employee.json()["id"],
        },
    )
    assert created.status_code == 201
    assert created.json()["employee_id"] == employee.json()["id"]

    inactive = client.delete(f"/api/v1/employees/{employee.json()['id']}", headers=headers)
    assert inactive.status_code == 200
    updated = client.patch(
        f"/api/v1/auth/users/{created.json()['id']}",
        headers=headers,
        json={
            "full_name": "Linked User Updated",
            "employee_id": employee.json()["id"],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["employee_id"] == employee.json()["id"]

    unlinked = client.patch(
        f"/api/v1/auth/users/{created.json()['id']}",
        headers=headers,
        json={"employee_id": None},
    )
    assert unlinked.status_code == 200
    assert unlinked.json()["employee_id"] is None

    employee_audits = list(
        db_session.scalars(
            select(AuditLog)
            .where(
                AuditLog.entity_type == "user",
                AuditLog.entity_id == str(created.json()["id"]),
            )
            .order_by(AuditLog.id)
        )
    )
    assert employee_audits[0].after_json is not None
    assert employee_audits[0].after_json["employee_id"] == employee.json()["id"]
    assert employee_audits[-1].before_json is not None
    assert employee_audits[-1].before_json["employee_id"] == employee.json()["id"]

    rejected = client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={
            "username": "inactive-link",
            "full_name": "Inactive Link",
            "password": "Staff-Password-123",
            "employee_id": employee.json()["id"],
        },
    )
    assert rejected.status_code == 422


def test_refresh_rotates_tokens_and_logout_revokes_session(
    client: TestClient, db_session: Session
) -> None:
    _, password = _admin(db_session)
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": password},
    )
    assert login.status_code == 200
    original = login.json()

    refreshed = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": original["refresh_token"]},
    )
    assert refreshed.status_code == 200
    rotated = refreshed.json()
    assert rotated["refresh_token"] != original["refresh_token"]
    assert (
        client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": original["refresh_token"]},
        ).status_code
        == 401
    )

    logged_out = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {rotated['access_token']}"},
    )
    assert logged_out.status_code == 204
    assert (
        client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": rotated["refresh_token"]},
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {rotated['access_token']}"},
        ).status_code
        == 401
    )
    assert db_session.scalar(select(AuditLog).where(AuditLog.action == "LOGIN")) is not None


def test_password_reset_email_link_is_single_use_and_audited(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin, password = _admin(db_session)
    admin.email = "admin@example.com"
    db_session.commit()
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_from_email", "noreply@example.com")
    sent_emails: list[tuple[str, str]] = []
    monkeypatch.setattr(
        service,
        "send_password_reset_email",
        lambda email, token: sent_emails.append((email, token)),
    )
    auth = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": password},
    ).json()
    headers = {"Authorization": f"Bearer {auth['access_token']}"}

    reset_request = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "ADMIN@example.com"},
    )
    assert reset_request.status_code == 200
    assert "reset link will be sent" in reset_request.json()["message"]
    assert sent_emails and sent_emails[0][0] == "ADMIN@example.com"
    reset_token = sent_emails[0][1]

    unknown_request = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "unknown@example.com"},
    )
    assert unknown_request.status_code == 200
    assert unknown_request.json() == reset_request.json()
    assert len(sent_emails) == 1

    changed = client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "New-Secret-123"},
    )
    assert changed.status_code == 204
    assert (
        client.post(
            "/api/v1/auth/reset-password",
            json={"token": reset_token, "new_password": "Another-Secret-123"},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "New-Secret-123"},
        ).status_code
        == 200
    )
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401

    assert (
        db_session.scalar(
            select(AuditLog).where(AuditLog.after_json["event"].as_string() == "password_reset")
        )
        is not None
    )


def test_change_password_keeps_new_session_and_invalidates_old_session(
    client: TestClient, db_session: Session
) -> None:
    _, password = _admin(db_session)
    old_session = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": password},
    ).json()
    old_headers = {"Authorization": f"Bearer {old_session['access_token']}"}

    invalid = client.post(
        "/api/v1/auth/change-password",
        headers=old_headers,
        json={"current_password": "wrong", "new_password": "Updated-Password"},
    )
    assert invalid.status_code == 400

    changed = client.post(
        "/api/v1/auth/change-password",
        headers=old_headers,
        json={
            "current_password": password,
            "new_password": "Updated-Password",
        },
    )
    assert changed.status_code == 200
    new_session = changed.json()
    assert (
        client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {new_session['access_token']}"},
        ).status_code
        == 200
    )
    assert client.get("/api/v1/auth/me", headers=old_headers).status_code == 401
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": password},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "Updated-Password"},
        ).status_code
        == 200
    )


def test_profile_user_and_role_changes_are_audited_and_soft_deletable(
    client: TestClient, db_session: Session
) -> None:
    admin, password = _admin(db_session)
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": password},
    ).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    profile = client.patch(
        "/api/v1/auth/me",
        headers=headers,
        json={
            "full_name": "Administrator Updated",
            "email": "admin@example.com",
            "mobile": "01712345678",
        },
    )
    assert profile.status_code == 200
    assert profile.json()["full_name"] == "Administrator Updated"

    permissions = client.get("/api/v1/auth/permissions", headers=headers).json()
    permission_ids = [
        item["id"]
        for item in permissions
        if item["code"] in {"auth.profile.read", "auth.profile.update"}
    ]
    created_role = client.post(
        "/api/v1/auth/roles",
        headers=headers,
        json={"name": "Staff", "description": "Limited access", "permission_ids": permission_ids},
    )
    assert created_role.status_code == 201
    role_id = created_role.json()["id"]

    created_user = client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={
            "username": "staff",
            "full_name": "Staff Member",
            "email": "staff@example.com",
            "password": "Staff-Password-123",
            "role_ids": [role_id],
        },
    )
    assert created_user.status_code == 201
    user_id = created_user.json()["id"]
    assert created_user.json()["roles"] == ["Staff"]

    staff_session = client.post(
        "/api/v1/auth/login",
        json={"username": "staff", "password": "Staff-Password-123"},
    ).json()
    staff_headers = {"Authorization": f"Bearer {staff_session['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=staff_headers).status_code == 200

    edited_user = client.patch(
        f"/api/v1/auth/users/{user_id}",
        headers=headers,
        json={"full_name": "Staff Member Updated"},
    )
    assert edited_user.status_code == 200
    assert edited_user.json()["full_name"] == "Staff Member Updated"

    deactivated_user = client.post(
        f"/api/v1/auth/users/{user_id}/deactivate",
        headers=headers,
    )
    assert deactivated_user.status_code == 200
    assert deactivated_user.json()["is_active"] is False
    assert client.get("/api/v1/auth/me", headers=staff_headers).status_code == 401
    activated_user = client.post(
        f"/api/v1/auth/users/{user_id}/activate",
        headers=headers,
    )
    assert activated_user.status_code == 200
    assert activated_user.json()["is_active"] is True
    staff_session = client.post(
        "/api/v1/auth/login",
        json={"username": "staff", "password": "Staff-Password-123"},
    ).json()
    staff_headers = {"Authorization": f"Bearer {staff_session['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=staff_headers).status_code == 200

    renamed_role = client.patch(
        f"/api/v1/auth/roles/{role_id}",
        headers=headers,
        json={"name": "Store Staff", "permission_ids": permission_ids},
    )
    assert renamed_role.status_code == 200
    assert renamed_role.json()["name"] == "Store Staff"
    assert (
        client.post(
            f"/api/v1/auth/roles/{role_id}/deactivate",
            headers=headers,
        ).status_code
        == 200
    )
    assert client.get("/api/v1/auth/me", headers=staff_headers).status_code == 403
    assert (
        client.post(
            f"/api/v1/auth/roles/{role_id}/activate",
            headers=headers,
        ).status_code
        == 200
    )
    assert client.get("/api/v1/auth/me", headers=staff_headers).status_code == 200

    assert db_session.scalar(select(AuditLog).where(AuditLog.entity_type == "user")) is not None
    assert db_session.scalar(select(AuditLog).where(AuditLog.entity_type == "role")) is not None
    assert admin.id is not None


def test_last_administrator_cannot_deactivate_or_remove_own_role(
    client: TestClient, db_session: Session
) -> None:
    admin, password = _admin(db_session)
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": password},
    ).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    admin_role = db_session.scalar(select(Role).where(Role.name == "Administrator"))
    assert admin_role is not None

    assert (
        client.post(
            f"/api/v1/auth/users/{admin.id}/deactivate",
            headers=headers,
        ).status_code
        == 409
    )
    assert (
        client.patch(
            f"/api/v1/auth/users/{admin.id}",
            headers=headers,
            json={"role_ids": []},
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/v1/auth/roles/{admin_role.id}/deactivate",
            headers=headers,
        ).status_code
        == 409
    )
    assert (
        client.patch(
            f"/api/v1/auth/roles/{admin_role.id}",
            headers=headers,
            json={"name": "Former Administrator"},
        ).status_code
        == 409
    )


def test_fifth_failed_attempt_locks_account(client: TestClient, db_session: Session) -> None:
    user = User(
        username="staff",
        full_name="Staff Member",
        password_hash="",
        is_active=True,
    )
    from app.core.security import hash_password

    user.password_hash = hash_password("Correct-Password")
    db_session.add(user)
    db_session.commit()

    for _ in range(5):
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "staff", "password": "wrong"},
        )
        assert response.status_code == 401

    db_session.refresh(user)
    assert user.failed_attempts == 5
    assert user.locked_until is not None
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"username": "staff", "password": "Correct-Password"},
        ).json()["detail"]
        == "Account is locked"
    )


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("get", "/api/v1/auth/me", None),
        ("get", "/", None),
        ("patch", "/api/v1/auth/me", {"full_name": "Changed"}),
        ("post", "/api/v1/auth/change-password", {}),
        ("post", "/api/v1/auth/logout", None),
        ("get", "/api/v1/auth/users", None),
        ("post", "/api/v1/auth/users", {}),
        ("patch", "/api/v1/auth/users/1", {}),
        ("get", "/api/v1/auth/users/1", None),
        ("post", "/api/v1/auth/users/1/deactivate", None),
        ("post", "/api/v1/auth/users/1/activate", None),
        ("get", "/api/v1/auth/roles", None),
        ("post", "/api/v1/auth/roles", {}),
        ("patch", "/api/v1/auth/roles/1", {}),
        ("post", "/api/v1/auth/roles/1/deactivate", None),
        ("post", "/api/v1/auth/roles/1/activate", None),
        ("get", "/api/v1/auth/permissions", None),
        ("get", "/api/v1/auth/audit-logs", None),
    ],
)
def test_auth_endpoints_require_permissions(
    client: TestClient,
    db_session: Session,
    method: str,
    path: str,
    payload: dict[str, object] | None,
) -> None:
    user = User(
        username="no-permissions",
        full_name="No Permissions",
        password_hash="not-used",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    tokens = issue_session(db_session, user, audit_login=False)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    response = client.request(method, path, json=payload, headers=headers)
    assert response.status_code == 403


def test_auth_schema_validation_rejects_invalid_inputs(
    client: TestClient, db_session: Session
) -> None:
    admin, password = _admin(db_session)
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": password},
    ).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    # Invalid mobile format in profile update
    res = client.patch(
        "/api/v1/auth/me",
        headers=headers,
        json={"full_name": "Admin", "mobile": "01234567890"},
    )
    assert res.status_code == 422

    # Invalid username format in user creation
    res = client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={
            "username": "invalid username with spaces",
            "full_name": "Test User",
            "password": "Password-123",
            "role_ids": [1],
        },
    )
    assert res.status_code == 422

    # Non-positive role ID in user creation
    res = client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={
            "username": "valid_user",
            "full_name": "Test User",
            "password": "Password-123",
            "role_ids": [0],
        },
    )
    assert res.status_code == 422
