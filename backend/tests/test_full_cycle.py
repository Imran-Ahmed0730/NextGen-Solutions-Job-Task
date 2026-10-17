from collections.abc import Generator
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.modules.auth.models import User
from app.modules.auth.seed import seed_initial_admin
from app.modules.boms.models import BOM
from app.modules.company_settings.models import CompanySetting
from app.modules.customers.models import Customer
from app.modules.document_numbering.models import DocumentSequence
from app.modules.expense_categories.models import ExpenseCategory
from app.modules.expenses.models import Expense
from app.modules.inventory.models import MovementType, StockBalance, StockTransaction
from app.modules.inventory.service import post_stock_movement
from app.modules.money_accounts.models import MoneyAccount, MoneyAccountType
from app.modules.money_transactions.models import MoneyTransaction
from app.modules.product_categories.models import ProductCategory
from app.modules.products.models import Product, ProductType
from app.modules.purchase_orders.models import PurchaseOrder
from app.modules.purchase_returns.models import PurchaseReturn
from app.modules.sales.models import SalesOrder
from app.modules.sales_invoices.models import SalesInvoice
from app.modules.sales_returns.models import SalesReturn
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
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_supplier_to_dashboard_full_business_cycle(
    client: TestClient,
    db_session: Session,
) -> None:
    seeded = seed_initial_admin(db_session)
    assert seeded.password is not None
    actor = db_session.scalar(select(User).where(User.username == seeded.username))
    assert actor is not None
    today = date.today()

    category = ProductCategory(name="Full cycle products")
    unit = Unit(name="Piece", code="FC", allow_decimal=True)
    warehouse = Warehouse(name="Full cycle warehouse", code="FC")
    supplier = Supplier(code="SUP-FC", name="Full cycle supplier")
    customer = Customer(code="CUS-FC", name="Full cycle customer")
    cash_account = MoneyAccount(
        name="Full cycle cash",
        type=MoneyAccountType.CASH,
        opening_balance=Decimal("100.00"),
    )
    bank_account = MoneyAccount(
        name="Full cycle bank",
        type=MoneyAccountType.BANK,
        opening_balance=Decimal("50.00"),
    )
    mfs_account = MoneyAccount(
        name="Full cycle MFS",
        type=MoneyAccountType.MFS,
        opening_balance=Decimal("25.00"),
    )
    expense_category = ExpenseCategory(name="Full cycle expense")
    db_session.add_all(
        [
            category,
            unit,
            warehouse,
            supplier,
            customer,
            cash_account,
            bank_account,
            mfs_account,
            expense_category,
        ]
    )
    db_session.flush()
    raw_product = Product(
        sku="FC-RAW",
        name="Full cycle raw material",
        type=ProductType.RAW,
        category_id=category.id,
        unit_id=unit.id,
        is_stocked=True,
    )
    finished_product = Product(
        sku="FC-FG",
        name="Full cycle finished good",
        type=ProductType.FINISHED,
        category_id=category.id,
        unit_id=unit.id,
        is_stocked=True,
        avg_cost=Decimal("10.0000"),
    )
    db_session.add_all([raw_product, finished_product])
    db_session.add(CompanySetting(key="receipt_tolerance_pct", value="0"))
    sequence_types = {
        "PURCHASE_ORDER": "PO-",
        "GOODS_RECEIPT": "GR-",
        "PURCHASE_RETURN": "PR-",
        "PRODUCTION_ORDER": "PROD-",
        "SALES_ORDER": "SO-",
        "DELIVERY": "DN-",
        "INVOICE": "INV-",
        "SALES_RETURN": "SR-",
        "CUSTOMER_COLLECTION": "COL-",
        "SUPPLIER_PAYMENT": "PAY-",
        "EXPENSE": "EXP-",
    }
    db_session.add_all(
        [
            DocumentSequence(
                doc_type=doc_type,
                prefix=prefix,
                year=today.year,
                last_number=0,
                padding=4,
            )
            for doc_type, prefix in sequence_types.items()
        ]
    )
    db_session.commit()
    post_stock_movement(
        db_session,
        product_id=finished_product.id,
        warehouse_id=warehouse.id,
        movement_type=MovementType.OPENING,
        qty_signed=Decimal("2.000"),
        unit_cost=Decimal("10.0000"),
        actor=actor,
    )
    db_session.commit()
    headers = _login(client, actor, seeded.password)

    purchase_order_response = client.post(
        "/api/v1/purchase/orders",
        headers=headers,
        json={
            "doc_date": today.isoformat(),
            "supplier_id": supplier.id,
            "warehouse_id": warehouse.id,
            "lines": [
                {
                    "product_id": raw_product.id,
                    "qty": "20.000",
                    "unit_price": "4.00",
                }
            ],
        },
    )
    assert purchase_order_response.status_code == 201, purchase_order_response.text
    purchase_order = purchase_order_response.json()
    approved_order = client.post(
        f"/api/v1/purchase/orders/{purchase_order['id']}/submit",
        headers=headers,
    )
    assert approved_order.status_code == 200, approved_order.text
    assert approved_order.json()["status"] == "APPROVED"

    receipt_response = client.post(
        "/api/v1/purchase/receipts",
        headers=headers,
        json={
            "doc_date": today.isoformat(),
            "po_id": purchase_order["id"],
            "lines": [
                {
                    "po_line_id": purchase_order["lines"][0]["id"],
                    "qty": "20.000",
                    "unit_cost": "4.0000",
                }
            ],
        },
    )
    assert receipt_response.status_code == 201, receipt_response.text
    receipt = receipt_response.json()

    sales_order_response = client.post(
        "/api/v1/sales/orders",
        headers=headers,
        json={
            "doc_date": today.isoformat(),
            "customer_id": customer.id,
            "warehouse_id": warehouse.id,
            "lines": [
                {
                    "product_id": finished_product.id,
                    "qty_ordered": "5.000",
                    "unit_price": "20.00",
                }
            ],
        },
    )
    assert sales_order_response.status_code == 201, sales_order_response.text
    sales_order = sales_order_response.json()
    sales_order_line = sales_order["lines"][0]
    reservation_response = client.post(
        f"/api/v1/sales/orders/{sales_order['id']}/lines/{sales_order_line['id']}/reservations",
        headers=headers,
        json={"qty": "2.000"},
    )
    assert reservation_response.status_code == 200, reservation_response.text

    bom_response = client.post(
        "/api/v1/production/boms",
        headers=headers,
        json={
            "code": "BOM-FC",
            "finished_product_id": finished_product.id,
            "output_qty": "1.000",
            "labor_cost_default": "0.00",
            "overhead_cost_default": "0.00",
            "lines": [{"raw_product_id": raw_product.id, "qty": "2.000"}],
        },
    )
    assert bom_response.status_code == 201, bom_response.text
    bom = bom_response.json()
    production_response = client.post(
        "/api/v1/production/orders",
        headers=headers,
        json={
            "doc_date": today.isoformat(),
            "bom_id": bom["id"],
            "sales_order_line_id": sales_order_line["id"],
            "planned_qty": "3.000",
            "warehouse_id": warehouse.id,
        },
    )
    assert production_response.status_code == 201, production_response.text
    production_order = production_response.json()
    started = client.post(
        f"/api/v1/production/orders/{production_order['id']}/start",
        headers=headers,
    )
    assert started.status_code == 200, started.text
    completed = client.post(
        f"/api/v1/production/orders/{production_order['id']}/complete",
        headers=headers,
        json={"actual_qty": "3.000", "labor_cost": "3.00", "overhead_cost": "3.00"},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["material_cost"] == "24.00"
    assert completed.json()["total_cost"] == "30.00"
    assert completed.json()["unit_cost"] == "10.0000"

    delivery_response = client.post(
        f"/api/v1/sales/orders/{sales_order['id']}/deliveries",
        headers=headers,
        json={
            "doc_date": today.isoformat(),
            "lines": [{"order_line_id": sales_order_line["id"], "qty": "5.000"}],
        },
    )
    assert delivery_response.status_code == 201, delivery_response.text
    delivery = delivery_response.json()
    assert delivery["lines"][0]["unit_cost_cogs"] == "10.0000"

    invoice_response = client.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "delivery_id": delivery["id"],
            "doc_date": today.isoformat(),
            "due_date": today.isoformat(),
        },
    )
    assert invoice_response.status_code == 201, invoice_response.text
    invoice = invoice_response.json()["invoice"]
    assert invoice["total"] == "100.00"
    assert invoice["cogs_total"] == "50.00"

    collection_response = client.post(
        "/api/v1/money/collections",
        headers=headers,
        json={
            "doc_date": today.isoformat(),
            "customer_id": customer.id,
            "account_id": cash_account.id,
            "amount": "40.00",
            "method_ref": "FULL-CYCLE",
        },
    )
    assert collection_response.status_code == 201, collection_response.text
    sales_return_response = client.post(
        "/api/v1/sales/returns",
        headers=headers,
        json={
            "doc_date": today.isoformat(),
            "invoice_id": invoice["id"],
            "lines": [{"invoice_line_id": invoice["lines"][0]["id"], "qty": "1.000"}],
        },
    )
    assert sales_return_response.status_code == 201, sales_return_response.text
    assert sales_return_response.json()["total"] == "20.00"

    purchase_return_response = client.post(
        "/api/v1/purchase/returns",
        headers=headers,
        json={
            "doc_date": today.isoformat(),
            "receipt_id": receipt["id"],
            "lines": [{"receipt_line_id": receipt["lines"][0]["id"], "qty": "1.000"}],
        },
    )
    assert purchase_return_response.status_code == 201, purchase_return_response.text
    assert purchase_return_response.json()["total"] == "4.00"
    payment_response = client.post(
        "/api/v1/money/supplier-payments",
        headers=headers,
        json={
            "doc_date": today.isoformat(),
            "supplier_id": supplier.id,
            "account_id": bank_account.id,
            "amount": "20.00",
        },
    )
    assert payment_response.status_code == 201, payment_response.text
    expense_response = client.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "doc_date": today.isoformat(),
            "category_id": expense_category.id,
            "account_id": mfs_account.id,
            "amount": "10.00",
            "paid_to": "Full cycle expense",
        },
    )
    assert expense_response.status_code == 201, expense_response.text
    assert expense_response.json()["status"] == "POSTED"

    customer_statement = client.get(
        f"/api/v1/customers/{customer.id}/statement",
        headers=headers,
    )
    supplier_statement = client.get(
        f"/api/v1/suppliers/{supplier.id}/statement",
        headers=headers,
    )
    dashboard_response = client.get(
        f"/api/v1/reports/dashboard?period_from={today.isoformat()}&period_to={today.isoformat()}",
        headers=headers,
    )
    assert customer_statement.status_code == 200, customer_statement.text
    assert supplier_statement.status_code == 200, supplier_statement.text
    assert dashboard_response.status_code == 200, dashboard_response.text
    dashboard = dashboard_response.json()
    assert Decimal(customer_statement.json()["balance"]) == Decimal("40.00")
    assert Decimal(supplier_statement.json()["balance"]) == Decimal("56.00")
    assert Decimal(str(dashboard["sales"])) == Decimal("80.00")
    assert Decimal(str(dashboard["purchases"])) == Decimal("76.00")
    assert Decimal(str(dashboard["collections"])) == Decimal("40.00")
    assert Decimal(str(dashboard["expenses"])) == Decimal("10.00")
    assert Decimal(str(dashboard["account_balances"]["CASH"])) == Decimal("140.00")
    assert Decimal(str(dashboard["account_balances"]["BANK"])) == Decimal("30.00")
    assert Decimal(str(dashboard["account_balances"]["MFS"])) == Decimal("15.00")
    assert Decimal(str(dashboard["customer_due"])) == Decimal("40.00")
    assert Decimal(str(dashboard["supplier_due"])) == Decimal("56.00")
    assert Decimal(str(dashboard["inventory_value"])) == Decimal("62.000000")
    assert dashboard["pending_orders"] == 0
    assert Decimal(str(dashboard["estimated_profit"])) == Decimal("30.00")

    raw_balance = db_session.get(StockBalance, (raw_product.id, warehouse.id))
    finished_balance = db_session.get(StockBalance, (finished_product.id, warehouse.id))
    assert raw_balance is not None and raw_balance.qty_on_hand == Decimal("13.000")
    assert finished_balance is not None and finished_balance.qty_on_hand == Decimal("1.000")
    for balance in (raw_balance, finished_balance):
        ledger_total = db_session.scalar(
            select(func.coalesce(func.sum(StockTransaction.qty_signed), 0)).where(
                StockTransaction.product_id == balance.product_id,
                StockTransaction.warehouse_id == balance.warehouse_id,
            )
        )
        assert Decimal(str(ledger_total)) == balance.qty_on_hand
    for money_account, expected in (
        (cash_account, Decimal("140.00")),
        (bank_account, Decimal("30.00")),
        (mfs_account, Decimal("15.00")),
    ):
        money_total = db_session.scalar(
            select(func.coalesce(func.sum(MoneyTransaction.amount_signed), 0)).where(
                MoneyTransaction.account_id == money_account.id
            )
        )
        assert money_account.opening_balance + money_total == expected
    assert db_session.scalar(select(func.count(PurchaseOrder.id))) == 1
    assert db_session.scalar(select(func.count(BOM.id))) == 1
    assert db_session.scalar(select(func.count(SalesOrder.id))) == 1
    assert db_session.scalar(select(func.count(SalesInvoice.id))) == 1
    assert db_session.scalar(select(func.count(SalesReturn.id))) == 1
    assert db_session.scalar(select(func.count(PurchaseReturn.id))) == 1
    assert db_session.scalar(select(func.count(Expense.id))) == 1
