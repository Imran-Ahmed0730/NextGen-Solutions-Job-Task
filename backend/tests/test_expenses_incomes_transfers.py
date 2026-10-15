from collections.abc import Generator
from decimal import Decimal

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
from app.modules.document_numbering.models import DocumentSequence
from app.modules.expense_categories.models import ExpenseCategory
from app.modules.fund_transfers import repository as fund_transfer_repository
from app.modules.income_categories.models import IncomeCategory
from app.modules.money_accounts.models import MoneyAccount, MoneyAccountType
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
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def money_ops_fixture(
    db_session: Session,
) -> tuple[User, str, ExpenseCategory, IncomeCategory, MoneyAccount, MoneyAccount]:
    admin = seed_initial_admin(db_session)
    assert admin.password is not None
    actor = db_session.scalar(select(User).where(User.username == admin.username))
    assert actor is not None

    exp_cat = ExpenseCategory(name="Office Supplies")
    inc_cat = IncomeCategory(name="Consulting")
    account1 = MoneyAccount(
        name="Main Cash",
        type=MoneyAccountType.CASH,
        opening_balance=Decimal("1000.00"),
        allow_overdraft=False,
    )
    account2 = MoneyAccount(
        name="Bank Account",
        type=MoneyAccountType.BANK,
        opening_balance=Decimal("500.00"),
        allow_overdraft=False,
    )
    db_session.add_all([exp_cat, inc_cat, account1, account2])
    db_session.flush()

    db_session.add_all(
        [
            DocumentSequence(
                doc_type="EXPENSE",
                prefix="EXP-",
                year=2026,
                last_number=0,
                padding=4,
            ),
            DocumentSequence(
                doc_type="INCOME",
                prefix="INC-",
                year=2026,
                last_number=0,
                padding=4,
            ),
            DocumentSequence(
                doc_type="FUND_TRANSFER",
                prefix="TRF-",
                year=2026,
                last_number=0,
                padding=4,
            ),
        ]
    )
    db_session.commit()
    return actor, admin.password, exp_cat, inc_cat, account1, account2


def _login(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_expense_flow_posts_money_and_updates_balance(
    client: TestClient,
    db_session: Session,
    money_ops_fixture: tuple[
        User, str, ExpenseCategory, IncomeCategory, MoneyAccount, MoneyAccount
    ],
) -> None:
    actor, password, exp_cat, _, account1, _ = money_ops_fixture
    headers = _login(client, actor.username, password)

    # 1. Options endpoint
    options_res = client.get("/api/v1/expenses/options", headers=headers)
    assert options_res.status_code == 200
    assert any(c["id"] == exp_cat.id for c in options_res.json()["categories"])

    # 2. Post valid expense
    payload = {
        "doc_date": "2026-10-15",
        "category_id": exp_cat.id,
        "account_id": account1.id,
        "amount": "250.00",
        "paid_to": "Stationery Shop",
        "note": "Office pens and paper",
    }
    create_res = client.post("/api/v1/expenses", headers=headers, json=payload)
    assert create_res.status_code == 201
    expense_data = create_res.json()
    assert expense_data["doc_no"] == "EXP-20260001"
    assert expense_data["amount"] == "250.00"

    # Verify money transaction
    txns = list(
        db_session.scalars(
            select(MoneyTransaction).where(MoneyTransaction.source_type == "EXPENSE")
        )
    )
    assert len(txns) == 1
    assert txns[0].amount_signed == Decimal("-250.00")
    assert txns[0].txn_type == MoneyTransactionType.EXPENSE
    assert txns[0].account_id == account1.id

    # Verify balance endpoint: 1000 - 250 = 750
    bal_res = client.get(
        f"/api/v1/money-transactions/accounts/{account1.id}/balance", headers=headers
    )
    assert bal_res.status_code == 200
    assert bal_res.json()["balance"] == "750.00"

    # Verify audit log
    audit = db_session.scalar(
        select(AuditLog).where(
            AuditLog.entity_type == "expense", AuditLog.entity_id == expense_data["id"]
        )
    )
    assert audit is not None
    assert audit.action == "CREATE"

    # List expenses
    list_res = client.get("/api/v1/expenses", headers=headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1


def test_expense_fails_on_insufficient_balance(
    client: TestClient,
    money_ops_fixture: tuple[
        User, str, ExpenseCategory, IncomeCategory, MoneyAccount, MoneyAccount
    ],
) -> None:
    actor, password, exp_cat, _, account1, _ = money_ops_fixture
    headers = _login(client, actor.username, password)

    # Balance is 1000, attempt 1500 without overdraft
    payload = {
        "doc_date": "2026-10-15",
        "category_id": exp_cat.id,
        "account_id": account1.id,
        "amount": "1500.00",
        "paid_to": "Fancy Store",
    }
    res = client.post("/api/v1/expenses", headers=headers, json=payload)
    assert res.status_code == 409
    assert res.json()["detail"] == "MONEY_ACCOUNT_INSUFFICIENT"


def test_income_flow_posts_money_and_updates_balance(
    client: TestClient,
    db_session: Session,
    money_ops_fixture: tuple[
        User, str, ExpenseCategory, IncomeCategory, MoneyAccount, MoneyAccount
    ],
) -> None:
    actor, password, _, inc_cat, account1, _ = money_ops_fixture
    headers = _login(client, actor.username, password)

    # Options endpoint
    options_res = client.get("/api/v1/incomes/options", headers=headers)
    assert options_res.status_code == 200
    assert any(c["id"] == inc_cat.id for c in options_res.json()["categories"])

    # Post income
    payload = {
        "doc_date": "2026-10-15",
        "category_id": inc_cat.id,
        "account_id": account1.id,
        "amount": "300.00",
        "note": "Consulting retainer",
    }
    create_res = client.post("/api/v1/incomes", headers=headers, json=payload)
    assert create_res.status_code == 201
    income_data = create_res.json()
    assert income_data["doc_no"] == "INC-20260001"
    assert income_data["amount"] == "300.00"

    # Verify money transaction
    txns = list(
        db_session.scalars(select(MoneyTransaction).where(MoneyTransaction.source_type == "INCOME"))
    )
    assert len(txns) == 1
    assert txns[0].amount_signed == Decimal("300.00")
    assert txns[0].txn_type == MoneyTransactionType.INCOME

    # Balance: 1000 + 300 = 1300
    bal_res = client.get(
        f"/api/v1/money-transactions/accounts/{account1.id}/balance", headers=headers
    )
    assert bal_res.status_code == 200
    assert bal_res.json()["balance"] == "1300.00"


def test_fund_transfer_posts_paired_transactions_atomically(
    client: TestClient,
    db_session: Session,
    money_ops_fixture: tuple[
        User, str, ExpenseCategory, IncomeCategory, MoneyAccount, MoneyAccount
    ],
) -> None:
    actor, password, _, _, account1, account2 = money_ops_fixture
    headers = _login(client, actor.username, password)

    # 1. Reject transfer to same account
    same_acc = {
        "doc_date": "2026-10-15",
        "from_account_id": account1.id,
        "to_account_id": account1.id,
        "amount": "100.00",
    }
    bad_res = client.post("/api/v1/fund-transfers", headers=headers, json=same_acc)
    assert bad_res.status_code == 422

    # 2. Transfer 200 from account1 (1000) to account2 (500)
    transfer_payload = {
        "doc_date": "2026-10-15",
        "from_account_id": account1.id,
        "to_account_id": account2.id,
        "amount": "200.00",
        "note": "Bank deposit",
    }
    res = client.post("/api/v1/fund-transfers", headers=headers, json=transfer_payload)
    assert res.status_code == 201
    transfer_data = res.json()
    assert transfer_data["doc_no"] == "TRF-20260001"

    # Verify balances: account1 = 800, account2 = 700
    bal1 = client.get(
        f"/api/v1/money-transactions/accounts/{account1.id}/balance", headers=headers
    ).json()["balance"]
    bal2 = client.get(
        f"/api/v1/money-transactions/accounts/{account2.id}/balance", headers=headers
    ).json()["balance"]
    assert bal1 == "800.00"
    assert bal2 == "700.00"

    # Verify total invariant: 800 + 700 = 1500 (equal to original sum 1000 + 500)
    assert Decimal(bal1) + Decimal(bal2) == Decimal("1500.00")

    # Verify paired transactions
    txns = list(
        db_session.scalars(
            select(MoneyTransaction)
            .where(MoneyTransaction.source_type == "FUND_TRANSFER")
            .order_by(MoneyTransaction.id.asc())
        )
    )
    assert len(txns) == 2
    assert txns[0].account_id == account1.id
    assert txns[0].amount_signed == Decimal("-200.00")
    assert txns[0].txn_type == MoneyTransactionType.TRANSFER_OUT
    assert txns[1].account_id == account2.id
    assert txns[1].amount_signed == Decimal("200.00")
    assert txns[1].txn_type == MoneyTransactionType.TRANSFER_IN


def test_reverse_direction_transfer_locks_accounts_in_id_order(
    client: TestClient,
    money_ops_fixture: tuple[
        User, str, ExpenseCategory, IncomeCategory, MoneyAccount, MoneyAccount
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor, password, _, _, lower_id_account, higher_id_account = money_ops_fixture
    headers = _login(client, actor.username, password)
    locked_ids: list[int] = []
    original_lock = fund_transfer_repository.get_account_for_update

    def track_lock(db: Session, account_id: int) -> MoneyAccount | None:
        locked_ids.append(account_id)
        return original_lock(db, account_id)

    monkeypatch.setattr(fund_transfer_repository, "get_account_for_update", track_lock)
    response = client.post(
        "/api/v1/fund-transfers",
        headers=headers,
        json={
            "doc_date": "2026-10-15",
            "from_account_id": higher_id_account.id,
            "to_account_id": lower_id_account.id,
            "amount": "25.00",
        },
    )

    assert response.status_code == 201
    assert locked_ids[:2] == sorted([lower_id_account.id, higher_id_account.id])


def test_account_ledger_endpoint(
    client: TestClient,
    money_ops_fixture: tuple[
        User, str, ExpenseCategory, IncomeCategory, MoneyAccount, MoneyAccount
    ],
) -> None:
    actor, password, exp_cat, inc_cat, account1, _ = money_ops_fixture
    headers = _login(client, actor.username, password)

    balances_res = client.get("/api/v1/money-transactions/accounts", headers=headers)
    assert balances_res.status_code == 200
    account_balance = next(
        item for item in balances_res.json() if item["account_id"] == account1.id
    )
    assert account_balance["account_name"] == "Main Cash"
    assert account_balance["opening_balance"] == "1000.00"
    assert account_balance["balance"] == "1000.00"

    # Post an expense: -100
    client.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "doc_date": "2026-10-15",
            "category_id": exp_cat.id,
            "account_id": account1.id,
            "amount": "100.00",
        },
    )

    # Post an income: +250
    client.post(
        "/api/v1/incomes",
        headers=headers,
        json={
            "doc_date": "2026-10-15",
            "category_id": inc_cat.id,
            "account_id": account1.id,
            "amount": "250.00",
        },
    )

    # Fetch ledger
    ledger_res = client.get(
        f"/api/v1/money-transactions/accounts/{account1.id}/ledger", headers=headers
    )
    assert ledger_res.status_code == 200
    ledger = ledger_res.json()
    assert ledger["account_name"] == "Main Cash"
    assert ledger["opening_balance"] == "1000.00"
    assert ledger["total_inflow"] == "250.00"
    assert ledger["total_outflow"] == "100.00"
    assert ledger["closing_balance"] == "1150.00"
    assert len(ledger["entries"]) == 2
    assert ledger["entries"][0]["running_balance"] == "900.00"
    assert ledger["entries"][1]["running_balance"] == "1150.00"


def test_money_operations_permissions(
    client: TestClient,
    db_session: Session,
    money_ops_fixture: tuple[
        User, str, ExpenseCategory, IncomeCategory, MoneyAccount, MoneyAccount
    ],
) -> None:
    _, _, exp_cat, inc_cat, account1, account2 = money_ops_fixture
    unauth_user = User(
        username="unauthorized_money_user",
        full_name="Unauthorized User",
        password_hash=hash_password("Pass-12345"),
    )
    db_session.add(unauth_user)
    db_session.commit()
    headers = _login(client, unauth_user.username, "Pass-12345")

    # Unauthorized requests should get 403
    assert client.get("/api/v1/expenses", headers=headers).status_code == 403
    assert client.get("/api/v1/expenses/options", headers=headers).status_code == 403
    assert (
        client.post(
            "/api/v1/expenses",
            headers=headers,
            json={
                "doc_date": "2026-10-15",
                "category_id": exp_cat.id,
                "account_id": account1.id,
                "amount": "10.00",
            },
        ).status_code
        == 403
    )

    assert client.get("/api/v1/incomes", headers=headers).status_code == 403
    assert client.get("/api/v1/incomes/options", headers=headers).status_code == 403
    assert (
        client.post(
            "/api/v1/incomes",
            headers=headers,
            json={
                "doc_date": "2026-10-15",
                "category_id": inc_cat.id,
                "account_id": account1.id,
                "amount": "10.00",
            },
        ).status_code
        == 403
    )

    assert client.get("/api/v1/fund-transfers", headers=headers).status_code == 403
    assert client.get("/api/v1/fund-transfers/options", headers=headers).status_code == 403
    assert (
        client.post(
            "/api/v1/fund-transfers",
            headers=headers,
            json={
                "doc_date": "2026-10-15",
                "from_account_id": account1.id,
                "to_account_id": account2.id,
                "amount": "10.00",
            },
        ).status_code
        == 403
    )

    assert (
        client.get(
            f"/api/v1/money-transactions/accounts/{account1.id}/ledger", headers=headers
        ).status_code
        == 403
    )
