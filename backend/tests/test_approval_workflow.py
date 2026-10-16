from collections.abc import Generator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.modules.approvals.models import ApprovalAction, ApprovalRequest, ApprovalRule
from app.modules.auth.models import Permission, Role, User
from app.modules.auth.seed import seed_initial_admin
from app.modules.document_numbering.models import DocumentSequence
from app.modules.expense_categories.models import ExpenseCategory
from app.modules.inventory.models import StockBalance, StockTransaction
from app.modules.money_accounts.models import MoneyAccount, MoneyAccountType
from app.modules.money_transactions.models import MoneyTransaction
from app.modules.product_categories.models import ProductCategory
from app.modules.products.models import Product, ProductType
from app.modules.suppliers.models import Supplier
from app.modules.units.models import Unit
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
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def approval_setup(
    db_session: Session,
) -> tuple[User, str, User, str, Role, ExpenseCategory, MoneyAccount, Supplier, Product, Warehouse]:
    seeded = seed_initial_admin(db_session)
    assert seeded.password is not None
    requester = db_session.scalar(select(User).where(User.username == seeded.username))
    assert requester is not None
    role = Role(name="Approval Reviewer", is_active=True)
    permissions = list(
        db_session.scalars(
            select(Permission).where(
                Permission.code.in_(("approvals.requests.read", "approvals.requests.decide"))
            )
        )
    )
    role.permissions = permissions
    requester.roles.append(role)
    approver = User(
        username="reviewer",
        full_name="Approval Reviewer",
        password_hash=hash_password("Reviewer-Password-123"),
        roles=[role],
        is_active=True,
    )
    category = ExpenseCategory(name="Office Expense")
    account = MoneyAccount(
        name="Main Cash",
        type=MoneyAccountType.CASH,
        opening_balance=Decimal("5000.00"),
        allow_overdraft=False,
    )
    supplier = Supplier(code="SUP-APP", name="Approval Supplier")
    unit = Unit(name="Each", code="ea", allow_decimal=True)
    product_category = ProductCategory(name="Materials")
    warehouse = Warehouse(name="Main Warehouse", code="MAIN")
    db_session.add_all([approver, category, account, supplier, unit, product_category, warehouse])
    db_session.flush()
    product = Product(
        sku="MAT-APP",
        name="Approval Material",
        type=ProductType.RAW,
        category_id=product_category.id,
        unit_id=unit.id,
        is_stocked=True,
        avg_cost=Decimal("10.0000"),
    )
    db_session.add(product)
    db_session.add_all(
        [
            DocumentSequence(
                doc_type="EXPENSE", prefix="EXP-", year=2026, last_number=0, padding=4
            ),
            DocumentSequence(
                doc_type="STOCK_ADJUSTMENT",
                prefix="ADJ-",
                year=2026,
                last_number=0,
                padding=4,
            ),
            DocumentSequence(
                doc_type="PURCHASE_ORDER",
                prefix="PO-",
                year=2026,
                last_number=0,
                padding=4,
            ),
        ]
    )
    for doc_type in ("EXPENSE", "STOCK_ADJUSTMENT", "PURCHASE_ORDER"):
        db_session.add(
            ApprovalRule(
                doc_type=doc_type,
                min_amount=(Decimal("245.00") if doc_type == "PURCHASE_ORDER" else Decimal("0.00")),
                max_amount=None,
                approver_role=role,
                is_active=True,
            )
        )
    db_session.commit()
    return (
        requester,
        seeded.password,
        approver,
        "Reviewer-Password-123",
        role,
        category,
        account,
        supplier,
        product,
        warehouse,
    )


def _login(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_expense_waits_for_approval_and_rejection_can_be_resubmitted(
    client: TestClient,
    db_session: Session,
    approval_setup: tuple[
        User, str, User, str, Role, ExpenseCategory, MoneyAccount, Supplier, Product, Warehouse
    ],
) -> None:
    requester, requester_password, approver, approver_password, _, category, account, *_ = (
        approval_setup
    )
    requester_headers = _login(client, requester.username, requester_password)
    approver_headers = _login(client, approver.username, approver_password)
    payload = {
        "doc_date": "2026-10-15",
        "category_id": category.id,
        "account_id": account.id,
        "amount": "250.00",
        "paid_to": "Stationery Shop",
    }

    created = client.post("/api/v1/expenses", headers=requester_headers, json=payload)
    assert created.status_code == 201
    expense = created.json()
    assert expense["status"] == "PENDING_APPROVAL"
    assert db_session.scalar(select(func.count(MoneyTransaction.id))) == 0

    own_inbox = client.get("/api/v1/approvals/requests", headers=requester_headers)
    assert own_inbox.status_code == 200
    assert own_inbox.json() == []
    inbox = client.get("/api/v1/approvals/requests", headers=approver_headers)
    assert inbox.status_code == 200
    assert inbox.json()[0]["doc_no"] == expense["doc_no"]
    request_id = inbox.json()[0]["id"]

    admin_role = db_session.scalar(select(Role).where(Role.name == "Administrator"))
    assert admin_role is not None
    wrong_role_user = User(
        username="wrong-role",
        full_name="Wrong Role",
        password_hash=hash_password("Wrong-Role-Password-123"),
        roles=[admin_role],
    )
    db_session.add(wrong_role_user)
    db_session.commit()
    wrong_role = client.post(
        f"/api/v1/approvals/requests/{request_id}/approve",
        headers=_login(client, wrong_role_user.username, "Wrong-Role-Password-123"),
        json={"note": None},
    )
    assert wrong_role.status_code == 403

    self_approval = client.post(
        f"/api/v1/approvals/requests/{request_id}/approve",
        headers=requester_headers,
        json={"note": "Requester cannot decide"},
    )
    assert self_approval.status_code == 403

    rejected = client.post(
        f"/api/v1/approvals/requests/{request_id}/reject",
        headers=approver_headers,
        json={"note": "Please correct the amount"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"
    assert (
        client.get(f"/api/v1/expenses/{expense['id']}", headers=requester_headers).json()["status"]
        == "DRAFT"
    )
    assert db_session.scalar(select(func.count(MoneyTransaction.id))) == 0

    edited = client.put(
        f"/api/v1/expenses/{expense['id']}",
        headers=requester_headers,
        json={**payload, "amount": "275.00"},
    )
    assert edited.status_code == 200
    assert edited.json()["status"] == "PENDING_APPROVAL"
    resubmitted_request = db_session.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.doc_id == expense["id"], ApprovalRequest.status == "PENDING"
        )
    )
    assert resubmitted_request is not None
    approved = client.post(
        f"/api/v1/approvals/requests/{resubmitted_request.id}/approve",
        headers=approver_headers,
        json={"note": "Corrected"},
    )
    assert approved.status_code == 200
    assert (
        client.get(f"/api/v1/expenses/{expense['id']}", headers=requester_headers).json()["status"]
        == "POSTED"
    )
    assert db_session.scalar(select(func.count(MoneyTransaction.id))) == 1
    assert db_session.scalar(select(func.count(ApprovalAction.id))) == 2


def test_stock_adjustment_is_not_posted_until_approved(
    client: TestClient,
    db_session: Session,
    approval_setup: tuple[
        User, str, User, str, Role, ExpenseCategory, MoneyAccount, Supplier, Product, Warehouse
    ],
) -> None:
    requester, requester_password, approver, approver_password, _, _, _, _, product, warehouse = (
        approval_setup
    )
    requester_headers = _login(client, requester.username, requester_password)
    approver_headers = _login(client, approver.username, approver_password)
    created = client.post(
        "/api/v1/inventory/adjustments",
        headers=requester_headers,
        json={
            "doc_date": "2026-10-15",
            "warehouse_id": warehouse.id,
            "reason": "Count correction",
            "lines": [{"product_id": product.id, "qty_signed": "2.000"}],
        },
    )
    assert created.status_code == 201
    adjustment = created.json()
    assert adjustment["status"] == "PENDING_APPROVAL"
    assert db_session.scalar(select(func.count(StockTransaction.id))) == 0

    request = db_session.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.doc_type == "STOCK_ADJUSTMENT",
            ApprovalRequest.doc_id == adjustment["id"],
        )
    )
    assert request is not None
    assert request.amount == Decimal("20.00")
    rejected = client.post(
        f"/api/v1/approvals/requests/{request.id}/reject",
        headers=approver_headers,
        json={"note": "Please recount"},
    )
    assert rejected.status_code == 200
    assert (
        client.get(
            f"/api/v1/inventory/adjustments/{adjustment['id']}",
            headers=requester_headers,
        ).json()["status"]
        == "DRAFT"
    )
    assert db_session.scalar(select(func.count(StockTransaction.id))) == 0

    resubmitted = client.put(
        f"/api/v1/inventory/adjustments/{adjustment['id']}",
        headers=requester_headers,
        json={
            "doc_date": "2026-10-15",
            "warehouse_id": warehouse.id,
            "reason": "Recounted correction",
            "lines": [{"product_id": product.id, "qty_signed": "3.000"}],
        },
    )
    assert resubmitted.status_code == 200
    assert resubmitted.json()["status"] == "PENDING_APPROVAL"
    request = db_session.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.doc_type == "STOCK_ADJUSTMENT",
            ApprovalRequest.doc_id == adjustment["id"],
            ApprovalRequest.status == "PENDING",
        )
    )
    assert request is not None
    approved = client.post(
        f"/api/v1/approvals/requests/{request.id}/approve",
        headers=approver_headers,
        json={"note": None},
    )
    assert approved.status_code == 200
    assert (
        client.get(
            f"/api/v1/inventory/adjustments/{adjustment['id']}",
            headers=requester_headers,
        ).json()["status"]
        == "POSTED"
    )
    assert db_session.scalar(select(func.count(StockTransaction.id))) == 1
    movement = db_session.scalar(
        select(StockTransaction).where(StockTransaction.source_type == "STOCK_ADJUSTMENT")
    )
    assert movement is not None
    assert movement.unit_cost == Decimal("10.0000")
    balance = db_session.get(StockBalance, (product.id, warehouse.id))
    assert balance is not None
    assert balance.qty_on_hand == Decimal("3.000")
    assert db_session.scalar(select(func.count(ApprovalAction.id))) == 2


def test_failed_stock_post_rolls_back_approval_decision(
    client: TestClient,
    db_session: Session,
    approval_setup: tuple[
        User,
        str,
        User,
        str,
        Role,
        ExpenseCategory,
        MoneyAccount,
        Supplier,
        Product,
        Warehouse,
    ],
) -> None:
    requester, requester_password, approver, approver_password, _, _, _, _, product, warehouse = (
        approval_setup
    )
    requester_headers = _login(client, requester.username, requester_password)
    approver_headers = _login(client, approver.username, approver_password)
    created = client.post(
        "/api/v1/inventory/adjustments",
        headers=requester_headers,
        json={
            "doc_date": "2026-10-15",
            "warehouse_id": warehouse.id,
            "reason": "Unverified damaged stock",
            "lines": [{"product_id": product.id, "qty_signed": "-1.000"}],
        },
    )
    assert created.status_code == 201
    request = db_session.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.doc_type == "STOCK_ADJUSTMENT",
            ApprovalRequest.doc_id == created.json()["id"],
        )
    )
    assert request is not None

    failed = client.post(
        f"/api/v1/approvals/requests/{request.id}/approve",
        headers=approver_headers,
        json={"note": None},
    )
    assert failed.status_code == 409
    db_session.refresh(request)
    assert request.status == "PENDING"
    assert db_session.scalar(select(func.count(ApprovalAction.id))) == 0
    assert db_session.scalar(select(func.count(StockTransaction.id))) == 0


def test_stock_adjustment_approval_uses_submitted_average_cost_snapshot(
    client: TestClient,
    db_session: Session,
    approval_setup: tuple[
        User,
        str,
        User,
        str,
        Role,
        ExpenseCategory,
        MoneyAccount,
        Supplier,
        Product,
        Warehouse,
    ],
) -> None:
    (
        requester,
        requester_password,
        approver,
        approver_password,
        _,
        _,
        _,
        _,
        product,
        warehouse,
    ) = approval_setup
    requester_headers = _login(client, requester.username, requester_password)
    approver_headers = _login(client, approver.username, approver_password)
    created = client.post(
        "/api/v1/inventory/adjustments",
        headers=requester_headers,
        json={
            "doc_date": "2026-10-15",
            "warehouse_id": warehouse.id,
            "reason": "Count correction",
            "lines": [{"product_id": product.id, "qty_signed": "2.000"}],
        },
    )
    assert created.status_code == 201
    request = db_session.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.doc_type == "STOCK_ADJUSTMENT",
            ApprovalRequest.doc_id == created.json()["id"],
        )
    )
    assert request is not None
    assert request.amount == Decimal("20.00")

    product.avg_cost = Decimal("60.0000")
    db_session.commit()
    response = client.post(
        f"/api/v1/approvals/requests/{request.id}/approve",
        headers=approver_headers,
        json={"note": None},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "APPROVED"
    movement = db_session.scalar(
        select(StockTransaction).where(StockTransaction.source_type == "STOCK_ADJUSTMENT")
    )
    assert movement is not None
    assert movement.unit_cost == Decimal("10.0000")


def test_purchase_order_uses_matching_rule_and_inbox_decision(
    client: TestClient,
    db_session: Session,
    approval_setup: tuple[
        User, str, User, str, Role, ExpenseCategory, MoneyAccount, Supplier, Product, Warehouse
    ],
) -> None:
    (
        requester,
        requester_password,
        approver,
        approver_password,
        _,
        _,
        _,
        supplier,
        product,
        warehouse,
    ) = approval_setup
    requester_headers = _login(client, requester.username, requester_password)
    approver_headers = _login(client, approver.username, approver_password)
    created = client.post(
        "/api/v1/purchase/orders",
        headers=requester_headers,
        json={
            "doc_date": "2026-10-15",
            "supplier_id": supplier.id,
            "warehouse_id": warehouse.id,
            "lines": [{"product_id": product.id, "qty": "10.000", "unit_price": "25.00"}],
            "discount": "5.00",
        },
    )
    assert created.status_code == 201
    submitted = client.post(
        f"/api/v1/purchase/orders/{created.json()['id']}/submit",
        headers=requester_headers,
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "PENDING_APPROVAL"
    inbox = client.get("/api/v1/approvals/requests", headers=approver_headers)
    request_entry = next(
        item for item in inbox.json() if item["doc_no"] == created.json()["doc_no"]
    )
    assert request_entry["amount"] == "245.00"
    request_id = request_entry["id"]

    approved = client.post(
        f"/api/v1/approvals/requests/{request_id}/approve",
        headers=approver_headers,
        json={"note": None},
    )
    assert approved.status_code == 200
    order = client.get(
        f"/api/v1/purchase/orders/{created.json()['id']}",
        headers=requester_headers,
    )
    assert order.status_code == 200
    assert order.json()["status"] == "APPROVED"
