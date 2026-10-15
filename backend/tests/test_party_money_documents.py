from collections.abc import Generator
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.modules.auth.models import AuditLog, User
from app.modules.auth.seed import seed_initial_admin
from app.modules.customers.models import Customer
from app.modules.direct_purchases.models import DirectPurchase
from app.modules.document_numbering.models import DocumentSequence
from app.modules.money_accounts.models import MoneyAccount, MoneyAccountType
from app.modules.money_collections.models import CustomerCollection
from app.modules.money_transactions.models import MoneyTransaction
from app.modules.supplier_payments.models import SupplierPayment
from app.modules.suppliers.models import Supplier
from app.modules.warehouses.models import Warehouse


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
def party_money_fixture(
    db_session: Session,
) -> tuple[User, str, Customer, Supplier, MoneyAccount, DirectPurchase]:
    admin = seed_initial_admin(db_session)
    assert admin.password is not None
    actor = db_session.scalar(select(User).where(User.username == admin.username))
    assert actor is not None
    customer = Customer(
        code="CUST-MONEY",
        name="Collection Customer",
        opening_due=Decimal("75.00"),
    )
    supplier = Supplier(
        code="SUP-MONEY",
        name="Payment Supplier",
        opening_due=Decimal("20.00"),
    )
    account = MoneyAccount(
        name="Money Test Cash",
        type=MoneyAccountType.CASH,
        opening_balance=Decimal("500.00"),
    )
    warehouse = Warehouse(code="MONEY-MAIN", name="Money Test Warehouse")
    db_session.add_all([customer, supplier, account, warehouse])
    db_session.flush()

    purchase = DirectPurchase(
        doc_no="DP-MONEY-0001",
        doc_date=date(2026, 10, 1),
        supplier_id=supplier.id,
        warehouse_id=warehouse.id,
        status="POSTED",
        total=Decimal("100.00"),
        paid_amount=Decimal("0.00"),
        created_by=actor.id,
    )
    db_session.add_all(
        [
            purchase,
            DocumentSequence(
                doc_type="CUSTOMER_COLLECTION",
                prefix="COL-",
                year=2026,
                last_number=0,
                padding=4,
            ),
            DocumentSequence(
                doc_type="SUPPLIER_PAYMENT",
                prefix="PAY-",
                year=2026,
                last_number=0,
                padding=4,
            ),
        ]
    )
    db_session.commit()
    return actor, admin.password, customer, supplier, account, purchase


def _login(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_customer_collection_posts_ledger_audit_and_statement(
    client: TestClient,
    db_session: Session,
    party_money_fixture: tuple[User, str, Customer, Supplier, MoneyAccount, DirectPurchase],
) -> None:
    actor, password, customer, _, account, _ = party_money_fixture
    headers = _login(client, actor.username, password)

    options = client.get("/api/v1/money/collections/options", headers=headers)
    assert options.status_code == 200
    assert options.json()["customers"][0]["id"] == customer.id
    assert options.json()["accounts"][0]["id"] == account.id

    response = client.post(
        "/api/v1/money/collections",
        headers=headers,
        json={
            "doc_date": "2026-10-15",
            "customer_id": customer.id,
            "account_id": account.id,
            "amount": "30.00",
            "method_ref": "RCPT-001",
        },
    )
    assert response.status_code == 201
    assert response.json()["status"] == "POSTED"
    assert Decimal(response.json()["amount"]) == Decimal("30.00")
    assert db_session.scalar(select(func.sum(MoneyTransaction.amount_signed))) == Decimal("30.00")
    collection = db_session.get(CustomerCollection, response.json()["id"])
    assert collection is not None
    assert collection.created_by == actor.id
    assert (
        db_session.scalar(
            select(func.count(AuditLog.id)).where(AuditLog.entity_type == "customer_collection")
        )
        == 1
    )

    statement = client.get(f"/api/v1/customers/{customer.id}/statement", headers=headers)
    assert statement.status_code == 200
    entries = statement.json()["entries"]
    assert entries[0]["type"] == "OPENING_BALANCE"
    assert entries[-1]["type"] == "COLLECTION"
    assert Decimal(statement.json()["balance"]) == Decimal("45.00")


def test_collection_rejects_overprecision_amount_without_creating_records(
    client: TestClient,
    db_session: Session,
    party_money_fixture: tuple[User, str, Customer, Supplier, MoneyAccount, DirectPurchase],
) -> None:
    actor, password, customer, _, account, _ = party_money_fixture
    headers = _login(client, actor.username, password)
    response = client.post(
        "/api/v1/money/collections",
        headers=headers,
        json={
            "doc_date": "2026-10-15",
            "customer_id": customer.id,
            "account_id": account.id,
            "amount": "30.001",
        },
    )
    assert response.status_code == 422
    assert db_session.scalar(select(CustomerCollection.id)) is None
    assert db_session.scalar(select(MoneyTransaction.id)) is None
    assert (
        db_session.scalar(
            select(func.count(AuditLog.id)).where(
                AuditLog.entity_type.in_(["customer_collection", "money_transaction"])
            )
        )
        == 0
    )


def test_collection_rejects_missing_account_without_creating_document(
    client: TestClient,
    db_session: Session,
    party_money_fixture: tuple[User, str, Customer, Supplier, MoneyAccount, DirectPurchase],
) -> None:
    actor, password, customer, _, _, _ = party_money_fixture
    headers = _login(client, actor.username, password)
    response = client.post(
        "/api/v1/money/collections",
        headers=headers,
        json={
            "doc_date": "2026-10-15",
            "customer_id": customer.id,
            "account_id": 9999,
            "amount": "30.00",
        },
    )
    assert response.status_code == 404
    assert db_session.scalar(select(CustomerCollection.id)) is None
    assert db_session.scalar(select(MoneyTransaction.id)) is None


def test_supplier_payment_rolls_back_when_account_balance_is_insufficient(
    client: TestClient,
    db_session: Session,
    party_money_fixture: tuple[User, str, Customer, Supplier, MoneyAccount, DirectPurchase],
) -> None:
    actor, password, _, supplier, account, _ = party_money_fixture
    headers = _login(client, actor.username, password)
    response = client.post(
        "/api/v1/money/supplier-payments",
        headers=headers,
        json={
            "doc_date": "2026-10-15",
            "supplier_id": supplier.id,
            "account_id": account.id,
            "amount": "600.00",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "MONEY_ACCOUNT_INSUFFICIENT"
    assert db_session.scalar(select(SupplierPayment.id)) is None
    assert db_session.scalar(select(MoneyTransaction.id)) is None
    assert (
        db_session.scalar(
            select(func.count(AuditLog.id)).where(
                AuditLog.entity_type.in_(["supplier_payment", "money_transaction"])
            )
        )
        == 0
    )


def test_supplier_payment_posts_bill_allocation_ledger_and_statement(
    client: TestClient,
    db_session: Session,
    party_money_fixture: tuple[User, str, Customer, Supplier, MoneyAccount, DirectPurchase],
) -> None:
    actor, password, _, supplier, account, purchase = party_money_fixture
    headers = _login(client, actor.username, password)

    options = client.get("/api/v1/money/supplier-payments/options", headers=headers)
    assert options.status_code == 200
    assert options.json()["suppliers"][0]["id"] == supplier.id
    assert options.json()["accounts"][0]["id"] == account.id
    bills = client.get(
        f"/api/v1/money/supplier-payments/bills?supplier_id={supplier.id}",
        headers=headers,
    )
    assert bills.status_code == 200
    assert bills.json()[0]["ref_id"] == purchase.id
    assert Decimal(bills.json()[0]["outstanding"]) == Decimal("100.00")

    response = client.post(
        "/api/v1/money/supplier-payments",
        headers=headers,
        json={
            "doc_date": "2026-10-15",
            "supplier_id": supplier.id,
            "account_id": account.id,
            "amount": "40.00",
            "allocations": [
                {"ref_type": "DIRECT_PURCHASE", "ref_id": purchase.id, "amount": "25.00"}
            ],
        },
    )
    assert response.status_code == 201
    assert len(response.json()["allocations"]) == 1
    transaction = db_session.scalar(select(MoneyTransaction))
    assert transaction is not None
    assert transaction.amount_signed == Decimal("-40.00")
    assert (
        db_session.scalar(
            select(func.count(AuditLog.id)).where(AuditLog.entity_type == "supplier_payment")
        )
        == 1
    )
    remaining_bills = client.get(
        f"/api/v1/money/supplier-payments/bills?supplier_id={supplier.id}",
        headers=headers,
    )
    assert remaining_bills.status_code == 200
    assert Decimal(remaining_bills.json()[0]["outstanding"]) == Decimal("75.00")

    excess_payment = client.post(
        "/api/v1/money/supplier-payments",
        headers=headers,
        json={
            "doc_date": "2026-10-16",
            "supplier_id": supplier.id,
            "account_id": account.id,
            "amount": "80.00",
            "allocations": [
                {"ref_type": "DIRECT_PURCHASE", "ref_id": purchase.id, "amount": "80.00"}
            ],
        },
    )
    assert excess_payment.status_code == 409
    assert db_session.scalar(select(func.count(SupplierPayment.id))) == 1

    statement = client.get(f"/api/v1/suppliers/{supplier.id}/statement", headers=headers)
    assert statement.status_code == 200
    assert statement.json()["entries"][0]["type"] == "OPENING_BALANCE"
    assert Decimal(statement.json()["balance"]) == Decimal("80.00")


def test_supplier_payment_rejects_overallocation_and_rolls_back(
    client: TestClient,
    db_session: Session,
    party_money_fixture: tuple[User, str, Customer, Supplier, MoneyAccount, DirectPurchase],
) -> None:
    actor, password, _, supplier, account, purchase = party_money_fixture
    headers = _login(client, actor.username, password)
    response = client.post(
        "/api/v1/money/supplier-payments",
        headers=headers,
        json={
            "doc_date": "2026-10-15",
            "supplier_id": supplier.id,
            "account_id": account.id,
            "amount": "110.00",
            "allocations": [
                {"ref_type": "DIRECT_PURCHASE", "ref_id": purchase.id, "amount": "110.00"}
            ],
        },
    )
    assert response.status_code == 409
    assert db_session.scalar(select(SupplierPayment.id)) is None
    assert db_session.scalar(select(MoneyTransaction.id)) is None
    assert (
        db_session.scalar(
            select(func.count(AuditLog.id)).where(
                AuditLog.entity_type.in_(["supplier_payment", "money_transaction"])
            )
        )
        == 0
    )


def test_supplier_payment_rejects_missing_account_without_creating_document(
    client: TestClient,
    db_session: Session,
    party_money_fixture: tuple[User, str, Customer, Supplier, MoneyAccount, DirectPurchase],
) -> None:
    actor, password, _, supplier, _, _ = party_money_fixture
    headers = _login(client, actor.username, password)
    response = client.post(
        "/api/v1/money/supplier-payments",
        headers=headers,
        json={
            "doc_date": "2026-10-15",
            "supplier_id": supplier.id,
            "account_id": 9999,
            "amount": "40.00",
        },
    )
    assert response.status_code == 404
    assert db_session.scalar(select(SupplierPayment.id)) is None
    assert db_session.scalar(select(MoneyTransaction.id)) is None


def test_party_money_routes_require_authentication(
    client: TestClient,
) -> None:
    assert client.get("/api/v1/money/collections").status_code == 401
    assert client.post("/api/v1/money/supplier-payments", json={}).status_code == 401


def test_party_money_routes_require_their_read_permission(
    client: TestClient,
    db_session: Session,
) -> None:
    viewer = User(
        username="money-viewer",
        full_name="Money Viewer",
        password_hash=hash_password("ViewerPass123!"),
    )
    db_session.add(viewer)
    db_session.commit()
    headers = _login(client, viewer.username, "ViewerPass123!")
    assert client.get("/api/v1/money/collections", headers=headers).status_code == 403
    assert client.get("/api/v1/money/supplier-payments", headers=headers).status_code == 403
