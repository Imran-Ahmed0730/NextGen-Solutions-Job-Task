from collections.abc import Generator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.modules.auth.models import AuditLog, Permission, User
from app.modules.auth.seed import seed_initial_admin
from app.modules.money_transactions.models import MoneyTransaction, MoneyTransactionType


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
def admin(db_session: Session) -> tuple[User, str]:
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


def _create_employee(client: TestClient, headers: dict[str, str], code: str) -> int:
    response = client.post(
        "/api/v1/employees",
        headers=headers,
        json={
            "code": code,
            "name": f"Employee {code}",
            "mobile": "01712345678",
            "join_date": "2025-01-01",
            "base_salary": "1000.00",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_money_account(
    client: TestClient, headers: dict[str, str], opening_balance: str
) -> int:
    response = client.post(
        "/api/v1/money-accounts",
        headers=headers,
        json={
            "name": "Payroll Bank",
            "type": "BANK",
            "opening_balance": opening_balance,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _configure_payroll_number(client: TestClient, headers: dict[str, str]) -> None:
    response = client.post(
        "/api/v1/document-numbering",
        headers=headers,
        json={"doc_type": "PAYROLL", "prefix": "PAY-", "year": 2026, "padding": 4},
    )
    assert response.status_code == 201


def test_payroll_draft_deductions_and_salary_posting_are_atomic(
    client: TestClient,
    db_session: Session,
    admin: tuple[User, str],
) -> None:
    actor, password = admin
    headers = _login(client, actor, password)
    first_employee = _create_employee(client, headers, "EMP-001")
    _create_employee(client, headers, "EMP-002")
    account_id = _create_money_account(client, headers, "2500.00")
    _configure_payroll_number(client, headers)

    created = client.post(
        "/api/v1/payroll/runs",
        headers=headers,
        json={"period_month": 10, "period_year": 2026},
    )
    assert created.status_code == 201
    run = created.json()
    assert run["status"] == "DRAFT"
    assert run["total_amount"] == "2000.00"
    assert len(run["lines"]) == 2
    line = next(item for item in run["lines"] if item["employee_id"] == first_employee)

    updated = client.patch(
        f"/api/v1/payroll/runs/{run['id']}/lines/{line['id']}",
        headers=headers,
        json={"deductions": "100.00"},
    )
    assert updated.status_code == 200
    assert updated.json()["total_amount"] == "1900.00"
    updated_line = next(
        item for item in updated.json()["lines"] if item["employee_id"] == first_employee
    )
    assert updated_line["net_pay"] == "900.00"

    posted = client.post(
        f"/api/v1/payroll/runs/{run['id']}/post",
        headers=headers,
        json={"account_id": account_id, "paid_on": "2026-10-31"},
    )
    assert posted.status_code == 200
    assert posted.json()["status"] == "POSTED"
    assert posted.json()["doc_no"] == "PAY-20260001"
    assert posted.json()["paid_on"] == "2026-10-31"
    assert all(item["paid_txn_id"] for item in posted.json()["lines"] if item["net_pay"] != "0.00")

    transactions = list(
        db_session.scalars(
            select(MoneyTransaction).where(
                MoneyTransaction.source_type == "PAYROLL",
                MoneyTransaction.source_id == run["id"],
            )
        )
    )
    assert len(transactions) == 2
    assert all(item.txn_type == MoneyTransactionType.SALARY for item in transactions)
    assert sum((item.amount_signed for item in transactions), Decimal("0.00")) == Decimal(
        "-1900.00"
    )
    assert [item.action for item in db_session.scalars(
        select(AuditLog).where(AuditLog.entity_type == "payroll_run")
    )] == ["CREATE", "UPDATE", "POST"]

    duplicate = client.post(
        "/api/v1/payroll/runs",
        headers=headers,
        json={"period_month": 10, "period_year": 2026},
    )
    assert duplicate.status_code == 409
    second_post = client.post(
        f"/api/v1/payroll/runs/{run['id']}/post",
        headers=headers,
        json={"account_id": account_id, "paid_on": "2026-10-31"},
    )
    assert second_post.status_code == 409
    assert len(transactions) == 2


def test_payroll_rejects_excess_deduction_and_rolls_back_insufficient_funds(
    client: TestClient,
    db_session: Session,
    admin: tuple[User, str],
) -> None:
    actor, password = admin
    headers = _login(client, actor, password)
    _create_employee(client, headers, "EMP-001")
    account_id = _create_money_account(client, headers, "100.00")
    _configure_payroll_number(client, headers)
    run = client.post(
        "/api/v1/payroll/runs",
        headers=headers,
        json={"period_month": 10, "period_year": 2026},
    ).json()

    line_id = run["lines"][0]["id"]
    excess = client.patch(
        f"/api/v1/payroll/runs/{run['id']}/lines/{line_id}",
        headers=headers,
        json={"deductions": "1000.01"},
    )
    assert excess.status_code == 422

    failed = client.post(
        f"/api/v1/payroll/runs/{run['id']}/post",
        headers=headers,
        json={"account_id": account_id, "paid_on": "2026-10-31"},
    )
    assert failed.status_code == 409
    run_after_failure = client.get(
        f"/api/v1/payroll/runs/{run['id']}", headers=headers
    ).json()
    assert run_after_failure["status"] == "DRAFT"
    assert (
        db_session.scalar(
            select(MoneyTransaction).where(MoneyTransaction.source_type == "PAYROLL")
        )
        is None
    )


def test_payroll_permission_denial_and_input_validation(
    client: TestClient,
    db_session: Session,
    admin: tuple[User, str],
) -> None:
    actor, password = admin
    headers = _login(client, actor, password)
    invalid = client.post(
        "/api/v1/payroll/runs",
        headers=headers,
        json={"period_month": 0, "period_year": 2026},
    )
    assert invalid.status_code == 422

    permission = db_session.scalar(
        select(Permission).where(Permission.code == "employees.payroll.read")
    )
    assert permission is not None
    actor.roles[0].permissions.remove(permission)
    db_session.commit()
    headers = _login(client, actor, password)
    assert client.get("/api/v1/payroll/runs", headers=headers).status_code == 403
