from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.modules.approvals.models import ApprovalRule
from app.modules.auth.models import AuditLog, Permission, Role, User
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
def admin(db_session: Session) -> tuple[User, str, Role]:
    seeded = seed_initial_admin(db_session)
    assert seeded.password is not None
    actor = db_session.scalar(select(User).where(User.username == seeded.username))
    assert actor is not None
    role = Role(name="Finance Approver", is_active=True)
    db_session.add(role)
    db_session.commit()
    return actor, seeded.password, role


def _login(client: TestClient, actor: User, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": actor.username, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def _rule_payload(role_id: int, min_amount: str, max_amount: str | None) -> dict[str, object]:
    return {
        "doc_type": "purchase_order",
        "min_amount": min_amount,
        "max_amount": max_amount,
        "approver_role_id": role_id,
    }


def test_approval_rule_create_update_ranges_and_audit(
    client: TestClient,
    db_session: Session,
    admin: tuple[User, str, Role],
) -> None:
    actor, password, role = admin
    headers = _login(client, actor, password)
    created = client.post(
        "/api/v1/approvals/rules",
        headers=headers,
        json=_rule_payload(role.id, "1000.00", "5000.00"),
    )
    assert created.status_code == 201
    rule = created.json()
    assert rule["doc_type"] == "PURCHASE_ORDER"
    assert rule["approver_role"]["name"] == "Finance Approver"

    overlap = client.post(
        "/api/v1/approvals/rules",
        headers=headers,
        json=_rule_payload(role.id, "5000.00", None),
    )
    assert overlap.status_code == 409
    adjacent = client.post(
        "/api/v1/approvals/rules",
        headers=headers,
        json=_rule_payload(role.id, "5000.01", None),
    )
    assert adjacent.status_code == 201

    update = client.patch(
        f"/api/v1/approvals/rules/{rule['id']}",
        headers=headers,
        json={"max_amount": "6000.00"},
    )
    assert update.status_code == 409
    updated = client.patch(
        f"/api/v1/approvals/rules/{rule['id']}",
        headers=headers,
        json={"max_amount": "4000.00", "approver_role_id": role.id},
    )
    assert updated.status_code == 200
    assert updated.json()["max_amount"] == "4000.00"

    audits = list(
        db_session.scalars(
            select(AuditLog).where(
                AuditLog.entity_type == "approval_rule",
                AuditLog.entity_id == str(rule["id"]),
            )
        )
    )
    assert [item.action for item in audits] == ["CREATE", "UPDATE"]
    assert audits[-1].before_json["max_amount"] == "5000.00"
    assert audits[-1].after_json["max_amount"] == "4000.00"


def test_approval_rule_deactivation_and_reactivation_overlap_validation(
    client: TestClient,
    db_session: Session,
    admin: tuple[User, str, Role],
) -> None:
    actor, password, role = admin
    headers = _login(client, actor, password)
    first = client.post(
        "/api/v1/approvals/rules",
        headers=headers,
        json=_rule_payload(role.id, "0.00", "999.99"),
    ).json()
    deactivated = client.post(f"/api/v1/approvals/rules/{first['id']}/deactivate", headers=headers)
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    overlapping = client.post(
        "/api/v1/approvals/rules",
        headers=headers,
        json=_rule_payload(role.id, "500.00", "1500.00"),
    )
    assert overlapping.status_code == 201

    reactivated = client.post(f"/api/v1/approvals/rules/{first['id']}/activate", headers=headers)
    assert reactivated.status_code == 409
    assert client.get("/api/v1/approvals/rules", headers=headers).json()[0]["is_active"] is True
    inactive = client.get("/api/v1/approvals/rules?include_inactive=true", headers=headers)
    assert len(inactive.json()) == 2
    assert [
        item.action
        for item in db_session.scalars(
            select(AuditLog).where(
                AuditLog.entity_type == "approval_rule",
                AuditLog.entity_id == str(first["id"]),
            )
        )
    ] == ["CREATE", "DEACTIVATE"]
    assert db_session.scalar(select(ApprovalRule).where(ApprovalRule.id == first["id"])) is not None


def test_approval_rule_validation_and_permission_denial(
    client: TestClient,
    db_session: Session,
    admin: tuple[User, str, Role],
) -> None:
    actor, password, role = admin
    headers = _login(client, actor, password)
    reversed_range = client.post(
        "/api/v1/approvals/rules",
        headers=headers,
        json=_rule_payload(role.id, "5000.00", "1000.00"),
    )
    assert reversed_range.status_code == 422
    wrong_role = client.post(
        "/api/v1/approvals/rules",
        headers=headers,
        json=_rule_payload(999, "0.00", None),
    )
    assert wrong_role.status_code == 404

    permission = db_session.scalar(
        select(Permission).where(Permission.code == "approvals.rules.read")
    )
    assert permission is not None
    actor.roles[0].permissions.remove(permission)
    db_session.commit()
    headers = _login(client, actor, password)
    assert client.get("/api/v1/approvals/rules", headers=headers).status_code == 403
