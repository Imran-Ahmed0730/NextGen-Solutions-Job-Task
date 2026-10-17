from collections.abc import Generator
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Literal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.core.database import Base, get_db
from app.main import app
from app.modules.auth.models import User
from app.modules.auth.seed import seed_initial_admin
from app.modules.customers.models import Customer
from app.modules.expense_categories.models import ExpenseCategory
from app.modules.expenses.models import Expense
from app.modules.inventory.models import StockBalance
from app.modules.money_accounts.models import MoneyAccount, MoneyAccountType
from app.modules.money_transactions.models import MoneyTransaction, MoneyTransactionType
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


def _login(client: TestClient, actor: User, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": actor.username, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def _run_reporting_views_migration(
    db_session: Session,
    direction: Literal["upgrade", "downgrade"],
) -> None:
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "20261111_reporting_views.py"
    )
    spec = spec_from_file_location("reporting_views_migration", migration_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load reporting views migration at {migration_path}")
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    migration_function = getattr(migration, direction, None)
    if not callable(migration_function):
        raise RuntimeError(f"Reporting views migration does not define {direction}()")
    with Operations.context(MigrationContext.configure(db_session.connection())):
        migration_function()


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
    customer = Customer(code="CUST-1", name="Customer", opening_due=Decimal("17.00"))
    supplier = Supplier(code="SUP-1", name="Supplier", opening_due=Decimal("19.00"))
    db_session.add_all([product, customer, supplier])
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
    _run_reporting_views_migration(db_session, "upgrade")
    _run_reporting_views_migration(db_session, "upgrade")

    stock_view = db_session.execute(
        text(
            "SELECT qty_on_hand, qty_reserved, qty_available, inventory_value "
            "FROM v_current_stock WHERE product_id = :product_id AND warehouse_id = :warehouse_id"
        ),
        {"product_id": product.id, "warehouse_id": warehouse.id},
    ).mappings().one()
    assert Decimal(str(stock_view["qty_on_hand"])) == Decimal("3.000")
    assert Decimal(str(stock_view["qty_reserved"])) == Decimal("1.000")
    assert Decimal(str(stock_view["qty_available"])) == Decimal("2.000")
    assert Decimal(str(stock_view["inventory_value"])) == Decimal("15.000000")

    account_view = db_session.execute(
        text("SELECT balance FROM v_account_balance WHERE account_id = :account_id"),
        {"account_id": account.id},
    ).scalar_one()
    assert Decimal(str(account_view)) == Decimal("125.00")
    customer_due_view = db_session.execute(
        text("SELECT due FROM v_customer_due WHERE customer_id = :customer_id"),
        {"customer_id": customer.id},
    ).scalar_one()
    supplier_due_view = db_session.execute(
        text("SELECT due FROM v_supplier_due WHERE supplier_id = :supplier_id"),
        {"supplier_id": supplier.id},
    ).scalar_one()
    assert Decimal(str(customer_due_view)) == Decimal("17.00")
    assert Decimal(str(supplier_due_view)) == Decimal("19.00")

    kpi_view = db_session.execute(
        text(
            "SELECT expenses, inventory_value, cash_balance, customer_due, supplier_due, "
            "estimated_profit FROM v_dashboard_kpis WHERE activity_date = :activity_date"
        ),
        {"activity_date": today},
    ).mappings().one()
    assert Decimal(str(kpi_view["expenses"])) == Decimal("12.50")
    assert Decimal(str(kpi_view["inventory_value"])) == Decimal("15.000000")
    assert Decimal(str(kpi_view["cash_balance"])) == Decimal("125.00")
    assert Decimal(str(kpi_view["customer_due"])) == Decimal("17.00")
    assert Decimal(str(kpi_view["supplier_due"])) == Decimal("19.00")
    assert Decimal(str(kpi_view["estimated_profit"])) == Decimal("-12.50")

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
    _run_reporting_views_migration(db_session, "downgrade")
    assert db_session.scalar(
        text("SELECT COUNT(*) FROM sqlite_master WHERE type = 'view' AND name LIKE 'v_%'")
    ) == 0


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
