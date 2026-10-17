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
from app.modules.assets.models import Asset
from app.modules.attendance.models import Attendance
from app.modules.auth.models import User
from app.modules.auth.seed import seed_initial_admin
from app.modules.boms.models import BOM
from app.modules.customers.models import Customer
from app.modules.employees.models import Employee
from app.modules.expense_categories.models import ExpenseCategory
from app.modules.expenses.models import Expense
from app.modules.goods_receipts.models import GoodsReceipt, GoodsReceiptLine
from app.modules.inventory.models import StockBalance
from app.modules.money_accounts.models import MoneyAccount, MoneyAccountType
from app.modules.money_collections.models import CustomerCollection
from app.modules.money_transactions.models import MoneyTransaction, MoneyTransactionType
from app.modules.payroll.models import PayrollRun
from app.modules.product_categories.models import ProductCategory
from app.modules.production_orders.models import ProductionOrder
from app.modules.products.models import Product, ProductType
from app.modules.purchase_orders.models import PurchaseOrder, PurchaseOrderLine
from app.modules.purchase_returns.models import PurchaseReturn, PurchaseReturnLine
from app.modules.sales.models import SalesDelivery, SalesOrder, SalesOrderLine
from app.modules.sales_invoices.models import SalesInvoice, SalesInvoiceLine
from app.modules.sales_returns.models import SalesReturn, SalesReturnLine
from app.modules.supplier_payments.models import SupplierPayment
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


def test_dashboard_figures_reconcile_with_seeded_report_totals(
    client: TestClient,
    db_session: Session,
) -> None:
    seeded = seed_initial_admin(db_session)
    assert seeded.password is not None
    actor = db_session.scalar(select(User).where(User.username == seeded.username))
    assert actor is not None
    today = date.today()
    category = ProductCategory(name="Reconciliation products")
    unit = Unit(name="Piece", code="REC")
    warehouse = Warehouse(name="Reconciliation warehouse", code="REC")
    customer = Customer(
        code="CUST-REC",
        name="Reconciliation customer",
        opening_due=Decimal("10.00"),
    )
    supplier = Supplier(
        code="SUP-REC",
        name="Reconciliation supplier",
        opening_due=Decimal("30.00"),
    )
    account = MoneyAccount(
        name="Reconciliation cash",
        type=MoneyAccountType.CASH,
        opening_balance=Decimal("100.00"),
    )
    expense_category = ExpenseCategory(name="Reconciliation expense")
    db_session.add_all(
        [category, unit, warehouse, customer, supplier, account, expense_category]
    )
    db_session.flush()
    product = Product(
        sku="REC-ACTIVE",
        name="Reconciliation active item",
        type=ProductType.FINISHED,
        category_id=category.id,
        unit_id=unit.id,
        is_stocked=True,
        avg_cost=Decimal("5.0000"),
    )
    inactive_product = Product(
        sku="REC-INACTIVE",
        name="Reconciliation inactive item",
        type=ProductType.RAW,
        category_id=category.id,
        unit_id=unit.id,
        is_stocked=True,
        is_active=False,
        reorder_level=Decimal("3.000"),
        avg_cost=Decimal("3.0000"),
    )
    product.reorder_level = Decimal("3.000")
    db_session.add_all([product, inactive_product])
    db_session.flush()

    order = SalesOrder(
        doc_no="SO-REC",
        doc_date=today,
        customer_id=customer.id,
        warehouse_id=warehouse.id,
        status="APPROVED",
        subtotal=Decimal("250.00"),
        discount=Decimal("0.00"),
        total=Decimal("250.00"),
    )
    db_session.add(order)
    db_session.flush()
    order_line = SalesOrderLine(
        order_id=order.id,
        product_id=product.id,
        qty_ordered=Decimal("10.000"),
        qty_delivered=Decimal("4.000"),
        unit_price=Decimal("25.00"),
        line_total=Decimal("250.00"),
    )
    db_session.add(order_line)
    db_session.flush()
    delivery = SalesDelivery(
        doc_no="DN-REC",
        doc_date=today,
        order_id=order.id,
        customer_id=customer.id,
        warehouse_id=warehouse.id,
    )
    db_session.add(delivery)
    db_session.flush()
    invoice = SalesInvoice(
        doc_no="INV-REC",
        doc_date=today,
        due_date=today + timedelta(days=10),
        customer_id=customer.id,
        delivery_id=delivery.id,
        subtotal=Decimal("100.00"),
        discount=Decimal("0.00"),
        total=Decimal("100.00"),
        cogs_total=Decimal("40.00"),
        created_by=actor.id,
    )
    db_session.add(invoice)
    db_session.flush()
    invoice_line = SalesInvoiceLine(
        invoice_id=invoice.id,
        product_id=product.id,
        qty=Decimal("4.000"),
        unit_price=Decimal("25.00"),
        line_total=Decimal("100.00"),
        unit_cost_cogs=Decimal("10.0000"),
    )
    db_session.add(invoice_line)
    db_session.flush()
    sales_return = SalesReturn(
        doc_no="SR-REC",
        doc_date=today,
        invoice_id=invoice.id,
        customer_id=customer.id,
        warehouse_id=warehouse.id,
        total=Decimal("20.00"),
        created_by=actor.id,
    )
    db_session.add(sales_return)
    db_session.flush()
    db_session.add(
        SalesReturnLine(
            return_id=sales_return.id,
            invoice_line_id=invoice_line.id,
            product_id=product.id,
            qty=Decimal("1.000"),
            unit_price=Decimal("25.00"),
            line_total=Decimal("20.00"),
            unit_cost_cogs=Decimal("8.0000"),
        )
    )

    purchase_order = PurchaseOrder(
        doc_no="PO-REC",
        doc_date=today,
        supplier_id=supplier.id,
        warehouse_id=warehouse.id,
        status="RECEIVED",
        subtotal=Decimal("100.00"),
        discount=Decimal("0.00"),
        total=Decimal("100.00"),
    )
    db_session.add(purchase_order)
    db_session.flush()
    purchase_order_line = PurchaseOrderLine(
        po_id=purchase_order.id,
        product_id=product.id,
        qty=Decimal("10.000"),
        unit_price=Decimal("10.00"),
        line_total=Decimal("100.00"),
        received_qty=Decimal("10.000"),
    )
    db_session.add(purchase_order_line)
    db_session.flush()
    receipt = GoodsReceipt(
        doc_no="GR-REC",
        doc_date=today,
        po_id=purchase_order.id,
        supplier_id=supplier.id,
        warehouse_id=warehouse.id,
        total=Decimal("100.00"),
        created_by=actor.id,
    )
    db_session.add(receipt)
    db_session.flush()
    receipt_line = GoodsReceiptLine(
        receipt_id=receipt.id,
        po_line_id=purchase_order_line.id,
        product_id=product.id,
        qty=Decimal("10.000"),
        unit_cost=Decimal("10.0000"),
        line_total=Decimal("100.00"),
    )
    db_session.add(receipt_line)
    db_session.flush()
    purchase_return = PurchaseReturn(
        doc_no="PR-REC",
        doc_date=today,
        receipt_id=receipt.id,
        supplier_id=supplier.id,
        warehouse_id=warehouse.id,
        total=Decimal("10.00"),
        created_by=actor.id,
    )
    db_session.add(purchase_return)
    db_session.flush()
    db_session.add(
        PurchaseReturnLine(
            return_id=purchase_return.id,
            receipt_line_id=receipt_line.id,
            product_id=product.id,
            qty=Decimal("1.000"),
            unit_cost=Decimal("10.0000"),
            line_total=Decimal("10.00"),
        )
    )
    collection = CustomerCollection(
        doc_no="COL-REC",
        doc_date=today,
        customer_id=customer.id,
        account_id=account.id,
        amount=Decimal("15.00"),
        created_by=actor.id,
    )
    payment = SupplierPayment(
        doc_no="PAY-REC",
        doc_date=today,
        supplier_id=supplier.id,
        account_id=account.id,
        amount=Decimal("20.00"),
        created_by=actor.id,
    )
    expense = Expense(
        doc_no="EXP-REC",
        doc_date=today,
        category_id=expense_category.id,
        account_id=account.id,
        amount=Decimal("5.00"),
        status="POSTED",
        created_by=actor.id,
    )
    db_session.add_all(
        [
            collection,
            payment,
            expense,
            MoneyTransaction(
                txn_date=datetime.combine(today, time.min),
                account_id=account.id,
                amount_signed=Decimal("15.00"),
                txn_type=MoneyTransactionType.COLLECTION,
            ),
            MoneyTransaction(
                txn_date=datetime.combine(today, time.min),
                account_id=account.id,
                amount_signed=Decimal("-20.00"),
                txn_type=MoneyTransactionType.PAYMENT,
            ),
            MoneyTransaction(
                txn_date=datetime.combine(today, time.min),
                account_id=account.id,
                amount_signed=Decimal("-5.00"),
                txn_type=MoneyTransactionType.EXPENSE,
            ),
            StockBalance(
                product_id=product.id,
                warehouse_id=warehouse.id,
                qty_on_hand=Decimal("3.000"),
                qty_reserved=Decimal("0.000"),
            ),
            StockBalance(
                product_id=inactive_product.id,
                warehouse_id=warehouse.id,
                qty_on_hand=Decimal("2.000"),
                qty_reserved=Decimal("0.000"),
            ),
        ]
    )
    db_session.commit()
    headers = _login(client, actor, seeded.password)
    period = f"period_from={today.isoformat()}&period_to={today.isoformat()}"
    dashboard_response = client.get(f"/api/v1/reports/dashboard?{period}", headers=headers)
    assert dashboard_response.status_code == 200
    dashboard = dashboard_response.json()

    def report_rows(report_type: str) -> list[dict[str, object]]:
        response = client.get(
            f"/api/v1/reports?report_type={report_type}&{period}",
            headers=headers,
        )
        assert response.status_code == 200, response.text
        return response.json()["rows"]

    sales_rows = report_rows("sales")
    purchase_rows = report_rows("purchases")
    expense_income_rows = report_rows("expense_income")
    cash_book_rows = report_rows("cash_book")
    customer_due_rows = report_rows("customer_due")
    supplier_due_rows = report_rows("supplier_due")
    stock_rows = report_rows("stock_valuation")
    profit_rows = report_rows("profit")
    low_stock_rows = report_rows("low_stock")
    _run_reporting_views_migration(db_session, "upgrade")
    pending_orders_from_status = db_session.scalar(
        text(
            "SELECT COUNT(DISTINCT order_id) FROM v_order_status WHERE qty_remaining > 0"
        )
    )

    def total(rows: list[dict[str, object]], key: str) -> Decimal:
        return sum(
            (Decimal(str(row[key])) for row in rows),
            Decimal("0.00"),
        )
    assert Decimal(str(dashboard["sales"])) == total(sales_rows, "amount")
    assert Decimal(str(dashboard["purchases"])) == total(purchase_rows, "amount")
    assert Decimal(str(dashboard["collections"])) == sum(
        (Decimal(str(row["amount"])) for row in cash_book_rows if row["type"] == "COLLECTION"),
        Decimal("0.00"),
    )
    assert Decimal(str(dashboard["expenses"])) == sum(
        (
            Decimal(str(row["amount"]))
            for row in expense_income_rows
            if row["type"] == "Expense"
        ),
        Decimal("0.00"),
    )
    assert Decimal(str(dashboard["customer_due"])) == total(customer_due_rows, "due")
    assert Decimal(str(dashboard["supplier_due"])) == total(supplier_due_rows, "due")
    assert Decimal(str(dashboard["inventory_value"])) == total(stock_rows, "value")
    assert [row["sku"] for row in low_stock_rows] == [product.sku]
    assert all(row["sku"] != inactive_product.sku for row in low_stock_rows)
    assert Decimal(str(dashboard["account_balances"]["CASH"])) == (
        account.opening_balance + total(cash_book_rows, "amount")
    )
    assert Decimal(str(dashboard["estimated_profit"])) == Decimal(
        str(profit_rows[0]["estimated_profit"])
    )
    assert Decimal(str(dashboard["sales"])) == Decimal("80.00")
    assert Decimal(str(dashboard["purchases"])) == Decimal("90.00")
    assert Decimal(str(dashboard["collections"])) == Decimal("15.00")
    assert Decimal(str(dashboard["expenses"])) == Decimal("5.00")
    assert Decimal(str(dashboard["customer_due"])) == Decimal("75.00")
    assert Decimal(str(dashboard["supplier_due"])) == Decimal("100.00")
    assert Decimal(str(dashboard["inventory_value"])) == Decimal("21.000000")
    assert Decimal(str(dashboard["account_balances"]["CASH"])) == Decimal("90.00")
    assert Decimal(str(dashboard["estimated_profit"])) == Decimal("43.00")
    assert dashboard["pending_orders"] == 1
    assert dashboard["pending_orders"] == pending_orders_from_status


def test_cash_book_date_range_includes_day_end_and_excludes_next_day(
    client: TestClient,
    db_session: Session,
) -> None:
    seeded = seed_initial_admin(db_session)
    assert seeded.password is not None
    actor = db_session.scalar(select(User).where(User.username == seeded.username))
    assert actor is not None
    today = date.today()
    account = MoneyAccount(name="Cash Book Range", type=MoneyAccountType.CASH)
    db_session.add(account)
    db_session.flush()
    db_session.add_all(
        [
            MoneyTransaction(
                txn_date=datetime.combine(today, time.min),
                account_id=account.id,
                amount_signed=Decimal("1.00"),
                txn_type=MoneyTransactionType.INCOME,
            ),
            MoneyTransaction(
                txn_date=datetime.combine(today, time.max),
                account_id=account.id,
                amount_signed=Decimal("2.00"),
                txn_type=MoneyTransactionType.INCOME,
            ),
            MoneyTransaction(
                txn_date=datetime.combine(today + timedelta(days=1), time.min),
                account_id=account.id,
                amount_signed=Decimal("3.00"),
                txn_type=MoneyTransactionType.INCOME,
            ),
        ]
    )
    db_session.commit()

    headers = _login(client, actor, seeded.password)
    response = client.get(
        "/api/v1/reports",
        params={
            "report_type": "cash_book",
            "period_from": today.isoformat(),
            "period_to": today.isoformat(),
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text
    rows = response.json()["rows"]
    assert [row["amount"] for row in rows] == ["1.00", "2.00"]


def test_production_asset_and_attendance_payroll_reports_return_seeded_data(
    client: TestClient,
    db_session: Session,
) -> None:
    seeded = seed_initial_admin(db_session)
    assert seeded.password is not None
    actor = db_session.scalar(select(User).where(User.username == seeded.username))
    assert actor is not None
    today = date.today()
    category = ProductCategory(name="Report coverage products")
    unit = Unit(name="Piece", code="RPT")
    warehouse = Warehouse(name="Report coverage warehouse", code="RPT")
    employee = Employee(
        code="EMP-RPT",
        name="Report coverage employee",
        join_date=today,
        base_salary=Decimal("500.00"),
    )
    asset = Asset(
        asset_code="AST-RPT",
        name="Report coverage asset",
        category="Equipment",
        purchase_date=today,
        purchase_cost=Decimal("250.00"),
        location="Main office",
        status="IN_USE",
        created_by=actor.id,
    )
    db_session.add_all([category, unit, warehouse, employee, asset])
    db_session.flush()
    product = Product(
        sku="RPT-FG",
        name="Report coverage finished good",
        type=ProductType.FINISHED,
        category_id=category.id,
        unit_id=unit.id,
        is_stocked=True,
        avg_cost=Decimal("7.5000"),
    )
    db_session.add(product)
    db_session.flush()
    bom = BOM(
        code="BOM-RPT",
        finished_product_id=product.id,
        output_qty=Decimal("1.000"),
    )
    db_session.add(bom)
    db_session.flush()
    db_session.add_all(
        [
            ProductionOrder(
                doc_no="PROD-RPT",
                doc_date=today,
                bom_id=bom.id,
                finished_product_id=product.id,
                planned_qty=Decimal("2.000"),
                actual_qty=Decimal("2.000"),
                warehouse_id=warehouse.id,
                status="COMPLETED",
                material_cost=Decimal("10.00"),
                labor_cost=Decimal("3.00"),
                overhead_cost=Decimal("2.00"),
                total_cost=Decimal("15.00"),
                unit_cost=Decimal("7.5000"),
                created_by=actor.id,
            ),
            Attendance(
                employee_id=employee.id,
                att_date=today,
                status="PRESENT",
            ),
            PayrollRun(
                doc_no="PAYROLL-RPT",
                period_month=today.month,
                period_year=today.year,
                status="POSTED",
                total_amount=Decimal("500.00"),
                paid_on=today,
                created_by=actor.id,
            ),
        ]
    )
    db_session.commit()
    headers = _login(client, actor, seeded.password)
    period = f"period_from={today.isoformat()}&period_to={today.isoformat()}"

    production = client.get(
        f"/api/v1/reports?report_type=production_cost&{period}",
        headers=headers,
    )
    assets = client.get(
        f"/api/v1/reports?report_type=assets&{period}",
        headers=headers,
    )
    attendance_payroll = client.get(
        f"/api/v1/reports?report_type=attendance_payroll&{period}",
        headers=headers,
    )

    assert production.status_code == 200
    assert production.json()["rows"] == [
        {
            "date": today.isoformat(),
            "document": "PROD-RPT",
            "status": "COMPLETED",
            "output_qty": "2.000",
            "material_cost": "10.00",
            "labor_cost": "3.00",
            "overhead_cost": "2.00",
            "total_cost": "15.00",
            "unit_cost": "7.5000",
        }
    ]
    assert assets.status_code == 200
    assert assets.json()["rows"] == [
        {
            "asset_code": "AST-RPT",
            "asset": "Report coverage asset",
            "category": "Equipment",
            "purchase_date": today.isoformat(),
            "purchase_cost": "250.00",
            "location": "Main office",
            "status": "IN_USE",
        }
    ]
    assert attendance_payroll.status_code == 200
    assert attendance_payroll.json()["rows"] == [
        {
            "date": today.isoformat(),
            "status": "PRESENT",
            "employee_count": 1,
        },
        {
            "year": today.year,
            "month": today.month,
            "document": "PAYROLL-RPT",
            "status": "POSTED",
            "total_amount": "500.00",
        },
    ]


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
