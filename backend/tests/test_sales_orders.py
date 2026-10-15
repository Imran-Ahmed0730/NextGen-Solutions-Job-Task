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
from app.modules.auth.models import AuditLog, Permission, Role, User
from app.modules.auth.seed import seed_initial_admin
from app.modules.customers.models import Customer
from app.modules.document_numbering.models import DocumentSequence
from app.modules.inventory.models import MovementType, StockBalance, StockTransaction
from app.modules.inventory.service import post_stock_movement
from app.modules.product_categories.models import ProductCategory
from app.modules.products.models import Product, ProductType
from app.modules.sales.models import SalesOrder
from app.modules.units.models import Unit
from app.modules.warehouses.models import Warehouse


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
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


def _login(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


@pytest.fixture
def sales_order_fixture(
    db_session: Session,
) -> tuple[User, str, Customer, Warehouse, Product]:
    result = seed_initial_admin(db_session)
    assert result.password is not None
    actor = db_session.scalar(select(User).where(User.username == result.username))
    assert actor is not None
    admin_role = db_session.scalar(select(Role).where(Role.name == "Administrator"))
    assert admin_role is not None
    permissions = [
        Permission(code=code, module="sales", description=code)
        for code in (
            "sales.orders.read",
            "sales.orders.create",
            "sales.orders.update",
            "sales.orders.reserve",
        )
    ]
    db_session.add_all(permissions)
    admin_role.permissions.extend(permissions)

    customer = Customer(code="CUS-SO-001", name="Sales Order Customer")
    category = ProductCategory(name="Sales Order Products")
    unit = Unit(name="Piece", code="pc", allow_decimal=True)
    warehouse = Warehouse(name="Sales Order Warehouse", code="SOWH")
    db_session.add_all([customer, category, unit, warehouse])
    db_session.flush()
    product = Product(
        sku="SO-001",
        name="Sales Order Product",
        type=ProductType.FINISHED,
        category_id=category.id,
        unit_id=unit.id,
        is_stocked=True,
    )
    db_session.add_all(
        [
            product,
            DocumentSequence(
                doc_type="SALES_ORDER",
                prefix="SO-",
                year=2026,
                last_number=0,
                padding=4,
            ),
        ]
    )
    db_session.commit()
    post_stock_movement(
        db_session,
        product_id=product.id,
        warehouse_id=warehouse.id,
        movement_type=MovementType.OPENING,
        qty_signed=Decimal("10.000"),
        actor=actor,
        unit_cost=Decimal("2.5000"),
    )
    db_session.commit()
    for record in (customer, warehouse, product):
        db_session.refresh(record)
    return actor, result.password, customer, warehouse, product


def _payload(customer: Customer, warehouse: Warehouse, product: Product) -> dict[str, object]:
    return {
        "doc_date": "2026-10-24",
        "customer_id": customer.id,
        "warehouse_id": warehouse.id,
        "delivery_date": "2026-10-30",
        "discount": "1.00",
        "note": "October order",
        "lines": [
            {"product_id": product.id, "qty_ordered": "3.250", "unit_price": "4.00"},
            {"product_id": product.id, "qty_ordered": "2.000", "unit_price": "2.50"},
        ],
    }


def test_sales_order_draft_create_edit_details_and_options(
    client: TestClient,
    db_session: Session,
    sales_order_fixture: tuple[User, str, Customer, Warehouse, Product],
) -> None:
    actor, password, customer, warehouse, product = sales_order_fixture
    headers = _login(client, actor.username, password)

    created = client.post(
        "/api/v1/sales/orders",
        headers=headers,
        json=_payload(customer, warehouse, product),
    )
    assert created.status_code == 201
    order = created.json()
    assert order["doc_no"] == "SO-20260001"
    assert order["status"] == "DRAFT"
    assert order["subtotal"] == "18.00"
    assert order["discount"] == "1.00"
    assert order["total"] == "17.00"
    assert [line["line_total"] for line in order["lines"]] == ["13.00", "5.00"]
    assert [line["qty_reserved"] for line in order["lines"]] == ["0.000", "0.000"]
    assert [line["reservations"] for line in order["lines"]] == [[], []]
    assert [line["qty_delivered"] for line in order["lines"]] == ["0.000", "0.000"]

    changed = _payload(customer, warehouse, product)
    changed["discount"] = "0.00"
    changed["lines"] = [{"product_id": product.id, "qty_ordered": "4.000", "unit_price": "2.00"}]
    updated = client.put(
        f"/api/v1/sales/orders/{order['id']}",
        headers=headers,
        json=changed,
    )
    assert updated.status_code == 200
    assert updated.json()["doc_no"] == "SO-20260001"
    assert updated.json()["total"] == "8.00"
    assert len(updated.json()["lines"]) == 1

    listing = client.get("/api/v1/sales/orders", headers=headers)
    detail = client.get(f"/api/v1/sales/orders/{order['id']}", headers=headers)
    options = client.get("/api/v1/sales/orders/options", headers=headers)
    assert listing.status_code == detail.status_code == options.status_code == 200
    assert listing.json()[0]["doc_no"] == "SO-20260001"
    assert detail.json()["id"] == order["id"]
    assert options.json()["customers"][0]["id"] == customer.id
    assert options.json()["warehouses"][0]["id"] == warehouse.id
    assert options.json()["products"][0]["id"] == product.id
    assert (
        db_session.scalar(
            select(func.count(AuditLog.id)).where(AuditLog.entity_type == "sales_order")
        )
        == 2
    )
    assert db_session.scalar(select(func.count(SalesOrder.id))) == 1


def test_sales_order_rejects_invalid_discount_and_inactive_warehouse(
    client: TestClient,
    db_session: Session,
    sales_order_fixture: tuple[User, str, Customer, Warehouse, Product],
) -> None:
    actor, password, customer, warehouse, product = sales_order_fixture
    headers = _login(client, actor.username, password)

    excessive_discount = _payload(customer, warehouse, product)
    excessive_discount["discount"] = "19.00"
    response = client.post("/api/v1/sales/orders", headers=headers, json=excessive_discount)
    assert response.status_code == 422
    assert response.json()["detail"] == "Discount cannot exceed the subtotal"

    inactive_warehouse = Warehouse(name="Inactive Warehouse", code="INACTIVE", is_active=False)
    db_session.add(inactive_warehouse)
    db_session.commit()
    invalid = _payload(customer, inactive_warehouse, product)
    response = client.post("/api/v1/sales/orders", headers=headers, json=invalid)
    assert response.status_code == 404

    whole_number_unit = Unit(name="Whole Piece", code="whole-pc", allow_decimal=False)
    db_session.add(whole_number_unit)
    db_session.flush()
    whole_product = Product(
        sku="SO-WHOLE",
        name="Whole Piece Product",
        type=ProductType.FINISHED,
        category_id=product.category_id,
        unit_id=whole_number_unit.id,
        is_stocked=True,
    )
    db_session.add(whole_product)
    db_session.commit()
    fractional_qty = _payload(customer, warehouse, product)
    fractional_qty["lines"] = [
        {"product_id": whole_product.id, "qty_ordered": "1.500", "unit_price": "1.00"}
    ]
    response = client.post(
        "/api/v1/sales/orders",
        headers=headers,
        json=fractional_qty,
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Product unit does not allow decimal quantity"

    oversized_total = _payload(customer, warehouse, product)
    oversized_total["lines"] = [
        {
            "product_id": product.id,
            "qty_ordered": "999999999999999.999",
            "unit_price": "9999999999999999.99",
        }
    ]
    response = client.post(
        "/api/v1/sales/orders",
        headers=headers,
        json=oversized_total,
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Sales order total exceeds supported amount"
    assert db_session.scalar(select(func.count(SalesOrder.id))) == 0


def test_sales_order_routes_require_permissions(
    client: TestClient,
    db_session: Session,
    sales_order_fixture: tuple[User, str, Customer, Warehouse, Product],
) -> None:
    _, _, customer, warehouse, product = sales_order_fixture
    assert client.get("/api/v1/sales/orders").status_code == 401
    assert client.get("/api/v1/sales/orders/options").status_code == 401

    readonly = User(
        username="sales_order_readonly",
        full_name="Sales Order Readonly",
        password_hash=hash_password("ReadOnly-Password-123"),
    )
    db_session.add(readonly)
    db_session.commit()
    headers = _login(client, readonly.username, "ReadOnly-Password-123")
    payload = _payload(customer, warehouse, product)
    assert client.get("/api/v1/sales/orders", headers=headers).status_code == 403
    assert client.get("/api/v1/sales/orders/options", headers=headers).status_code == 403
    assert client.post("/api/v1/sales/orders", headers=headers, json=payload).status_code == 403


def test_reserve_and_release_order_line_stock_and_lock_draft_edits(
    client: TestClient,
    db_session: Session,
    sales_order_fixture: tuple[User, str, Customer, Warehouse, Product],
) -> None:
    actor, password, customer, warehouse, product = sales_order_fixture
    headers = _login(client, actor.username, password)
    created = client.post(
        "/api/v1/sales/orders",
        headers=headers,
        json={
            **_payload(customer, warehouse, product),
            "lines": [{"product_id": product.id, "qty_ordered": "4.000", "unit_price": "5.00"}],
        },
    )
    assert created.status_code == 201
    order = created.json()
    line = order["lines"][0]

    reserved = client.post(
        f"/api/v1/sales/orders/{order['id']}/lines/{line['id']}/reservations",
        headers=headers,
        json={"qty": "3.000"},
    )
    assert reserved.status_code == 200
    reserved_line = reserved.json()["lines"][0]
    assert reserved_line["qty_reserved"] == "3.000"
    assert reserved_line["reservations"][0]["status"] == "ACTIVE"
    balance = db_session.get(StockBalance, (product.id, warehouse.id))
    assert balance is not None
    assert balance.qty_on_hand == Decimal("10.000")
    assert balance.qty_reserved == Decimal("3.000")
    assert db_session.scalar(select(func.count(StockTransaction.id))) == 1

    changed_payload = {
        **_payload(customer, warehouse, product),
        "lines": [{"product_id": product.id, "qty_ordered": "5.000", "unit_price": "5.00"}],
    }
    blocked_edit = client.put(
        f"/api/v1/sales/orders/{order['id']}",
        headers=headers,
        json=changed_payload,
    )
    assert blocked_edit.status_code == 409
    assert blocked_edit.json()["detail"] == "SALES_ORDER_HAS_RESERVATION_HISTORY"

    reservation_id = reserved_line["reservations"][0]["id"]
    released = client.delete(
        f"/api/v1/sales/orders/{order['id']}/reservations/{reservation_id}",
        headers=headers,
    )
    assert released.status_code == 200
    released_line = released.json()["lines"][0]
    assert released_line["qty_reserved"] == "0.000"
    assert released_line["reservations"][0]["status"] == "RELEASED"
    assert balance.qty_on_hand == Decimal("10.000")
    assert balance.qty_reserved == Decimal("0.000")

    blocked_after_release = client.put(
        f"/api/v1/sales/orders/{order['id']}",
        headers=headers,
        json=changed_payload,
    )
    assert blocked_after_release.status_code == 409


def test_order_reservation_rejects_foreign_lines_and_missing_permission(
    client: TestClient,
    db_session: Session,
    sales_order_fixture: tuple[User, str, Customer, Warehouse, Product],
) -> None:
    actor, password, customer, warehouse, product = sales_order_fixture
    readonly = User(
        username="sales_order_reservation_readonly",
        full_name="Sales Order Reservation Readonly",
        password_hash=hash_password("ReadOnly-Password-123"),
    )
    db_session.add(readonly)
    db_session.commit()
    headers = _login(client, readonly.username, "ReadOnly-Password-123")
    created = client.post(
        "/api/v1/sales/orders",
        headers=_login(client, actor.username, password),
        json=_payload(customer, warehouse, product),
    )
    assert created.status_code == 201
    order = created.json()
    line_id = order["lines"][0]["id"]

    denied = client.post(
        f"/api/v1/sales/orders/{order['id']}/lines/{line_id}/reservations",
        headers=headers,
        json={"qty": "1.000"},
    )
    assert denied.status_code == 403
