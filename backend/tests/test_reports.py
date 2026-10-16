from collections.abc import Generator
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.modules.auth.models import User
from app.modules.auth.seed import seed_initial_admin
from app.modules.expense_categories.models import ExpenseCategory
from app.modules.expenses.models import Expense
from app.modules.inventory.models import StockBalance
from app.modules.money_accounts.models import MoneyAccount, MoneyAccountType
from app.modules.money_transactions.models import MoneyTransaction, MoneyTransactionType
from app.modules.product_categories.models import ProductCategory
from app.modules.products.models import Product, ProductType
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


def _login(client: TestClient, actor: User, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": actor.username, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_dashboard_returns_ledger_backed_balances_and_period_expenses(
    client: TestClient,
    db_session: Session,
) -> None:
    seeded = seed_initial_admin(db_session)
    assert seeded.password is not None
    actor = db_session.scalar(select(User).where(User.username == seeded.username))
    assert actor is not None
    today = date.today()

    account = MoneyAccount(
        name="Main cash",
        type=MoneyAccountType.CASH,
        opening_balance=Decimal("100.00"),
    )
    category = ExpenseCategory(name="Office")
    unit = Unit(name="Piece", code="PC")
    product_category = ProductCategory(name="Materials")
    warehouse = Warehouse(name="Main", code="MAIN")
    db_session.add_all([account, category, unit, product_category, warehouse])
    db_session.flush()
    product = Product(
        sku="MAT-1",
        name="Material",
        type=ProductType.RAW,
        category_id=product_category.id,
        unit_id=unit.id,
        is_stocked=True,
        avg_cost=Decimal("5.0000"),
    )
    db_session.add(product)
    db_session.flush()
    db_session.add_all(
        [
            MoneyTransaction(
                txn_date=datetime.combine(today, time.min),
                account_id=account.id,
                amount_signed=Decimal("25.00"),
                txn_type=MoneyTransactionType.INCOME,
            ),
            Expense(
                doc_no="EXP-TEST",
                doc_date=today,
                category_id=category.id,
                account_id=account.id,
                amount=Decimal("12.50"),
                status="POSTED",
            ),
            StockBalance(
                product_id=product.id,
                warehouse_id=warehouse.id,
                qty_on_hand=Decimal("3.000"),
                qty_reserved=Decimal("1.000"),
            ),
        ]
    )
    db_session.commit()

    response = client.get(
        f"/api/v1/reports/dashboard?period_from={today.isoformat()}&period_to={today.isoformat()}",
        headers=_login(client, actor, seeded.password),
    )

    assert response.status_code == 200
    payload = response.json()
    assert Decimal(str(payload["account_balances"]["CASH"])) == Decimal("125.00")
    assert Decimal(str(payload["inventory_value"])) == Decimal("15.000000")
    assert Decimal(str(payload["expenses"])) == Decimal("12.50")
    assert Decimal(str(payload["estimated_profit"])) == Decimal("-12.50")
    assert payload["pending_orders"] == 0
    profit_report = client.get(
        f"/api/v1/reports?report_type=profit&period_from={today.isoformat()}"
        f"&period_to={today.isoformat()}",
        headers=_login(client, actor, seeded.password),
    )
    assert profit_report.status_code == 200
    profit_row = profit_report.json()["rows"][0]
    assert Decimal(str(profit_row["estimated_profit"])) == Decimal(str(payload["estimated_profit"]))
    assert Decimal(str(profit_row["estimated_profit"])) == (
        Decimal(str(profit_row["sales"]))
        - Decimal(str(profit_row["cogs"]))
        - Decimal(str(profit_row["expenses"]))
    )
    stock_report = client.get(
        f"/api/v1/reports?report_type=stock_valuation&period_from={today.isoformat()}"
        f"&period_to={today.isoformat()}",
        headers=_login(client, actor, seeded.password),
    )
    assert stock_report.status_code == 200
    assert sum(
        (Decimal(str(row["value"])) for row in stock_report.json()["rows"]),
        Decimal("0"),
    ) == Decimal(str(payload["inventory_value"]))


def test_dashboard_rejects_reversed_date_range(
    client: TestClient,
    db_session: Session,
) -> None:
    seeded = seed_initial_admin(db_session)
    assert seeded.password is not None
    actor = db_session.scalar(select(User).where(User.username == seeded.username))
    assert actor is not None
    today = date.today()

    response = client.get(
        f"/api/v1/reports/dashboard?period_from={today.isoformat()}"
        f"&period_to={(today - timedelta(days=1)).isoformat()}",
        headers=_login(client, actor, seeded.password),
    )

    assert response.status_code == 422


def test_report_options_and_filter_validation(
    client: TestClient,
    db_session: Session,
) -> None:
    seeded = seed_initial_admin(db_session)
    assert seeded.password is not None
    actor = db_session.scalar(select(User).where(User.username == seeded.username))
    assert actor is not None
    headers = _login(client, actor, seeded.password)

    options = client.get("/api/v1/reports/options", headers=headers)
    assert options.status_code == 200
    assert set(options.json()) == {"customers", "suppliers", "products", "warehouses"}

    invalid_filter = client.get(
        "/api/v1/reports?report_type=sales&warehouse_id=1",
        headers=headers,
    )
    assert invalid_filter.status_code == 422


@pytest.mark.parametrize(
    "report_type",
    [
        "sales",
        "purchases",
        "stock_valuation",
        "low_stock",
        "customer_due",
        "supplier_due",
        "production_cost",
        "cash_book",
        "expense_income",
        "profit",
        "assets",
        "attendance_payroll",
    ],
)
def test_report_center_returns_valid_report_shape(
    client: TestClient,
    db_session: Session,
    report_type: str,
) -> None:
    seeded = seed_initial_admin(db_session)
    assert seeded.password is not None
    actor = db_session.scalar(select(User).where(User.username == seeded.username))
    assert actor is not None
    today = date.today()

    response = client.get(
        f"/api/v1/reports?report_type={report_type}&period_from={today.isoformat()}"
        f"&period_to={today.isoformat()}",
        headers=_login(client, actor, seeded.password),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["report_type"] == report_type
    assert payload["period_from"] == today.isoformat()
    assert isinstance(payload["columns"], list)
    assert isinstance(payload["rows"], list)
