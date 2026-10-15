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
from app.modules.auth.models import AuditLog, User
from app.modules.auth.seed import seed_initial_admin
from app.modules.company_settings.models import CompanySetting
from app.modules.customers.models import Customer
from app.modules.document_numbering.models import DocumentSequence
from app.modules.inventory.models import (
    MovementType,
    StockBalance,
    StockReservation,
    StockTransaction,
)
from app.modules.inventory.service import post_stock_movement
from app.modules.product_categories.models import ProductCategory
from app.modules.products.models import Product, ProductType
from app.modules.sales.models import SalesDelivery, SalesDeliveryLine, SalesOrder
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
        avg_cost=Decimal("2.5000"),
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
            DocumentSequence(
                doc_type="DELIVERY",
                prefix="DN-",
                year=2026,
                last_number=0,
                padding=4,
            ),
            DocumentSequence(
                doc_type="INVOICE",
                prefix="INV-",
                year=2026,
                last_number=0,
                padding=4,
            ),
            DocumentSequence(
                doc_type="SALES_RETURN",
                prefix="SR-",
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


def test_post_delivery_consumes_reserved_or_available_stock_and_records_cogs(
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
            "lines": [{"product_id": product.id, "qty_ordered": "5.000", "unit_price": "5.00"}],
        },
    )
    assert created.status_code == 201
    order = created.json()
    line = order["lines"][0]

    response = client.post(
        f"/api/v1/sales/orders/{order['id']}/deliveries",
        headers=headers,
        json={
            "doc_date": "2026-10-25",
            "lines": [{"order_line_id": line["id"], "qty": "3.000"}],
        },
    )
    assert response.status_code == 201
    delivery = response.json()
    assert delivery["doc_no"] == "DN-20260001"
    assert delivery["status"] == "POSTED"
    assert delivery["lines"][0]["qty"] == "3.000"
    assert delivery["lines"][0]["unit_cost_cogs"] == "2.5000"
    db_session.expire_all()
    delivery_record = db_session.get(SalesDelivery, delivery["id"])
    assert delivery_record is not None
    delivery_line = db_session.scalar(
        select(SalesDeliveryLine).where(SalesDeliveryLine.delivery_id == delivery_record.id)
    )
    assert delivery_line is not None
    assert delivery_line.unit_cost_cogs == Decimal("2.5000")
    updated_order = client.get(f"/api/v1/sales/orders/{order['id']}", headers=headers).json()
    assert updated_order["status"] == "DRAFT"
    assert updated_order["lines"][0]["qty_delivered"] == "3.000"
    assert updated_order["deliveries"][0]["doc_no"] == "DN-20260001"
    balance = db_session.get(StockBalance, (product.id, warehouse.id))
    assert balance is not None
    assert balance.qty_on_hand == Decimal("7.000")
    assert balance.qty_reserved == Decimal("0.000")
    delivery_movement = db_session.scalar(
        select(StockTransaction).where(
            StockTransaction.movement_type == MovementType.SALE_DELIVERY
        )
    )
    assert delivery_movement is not None
    assert delivery_movement.qty_signed == Decimal("-3.000")
    assert delivery_movement.unit_cost == Decimal("2.5000")
    assert (
        db_session.scalar(
            select(func.count(AuditLog.id)).where(AuditLog.entity_type == "delivery")
        )
        == 1
    )


def test_delivery_consumes_existing_reservation_before_available_stock(
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
            "lines": [{"product_id": product.id, "qty_ordered": "5.000", "unit_price": "5.00"}],
        },
    )
    order = created.json()
    line = order["lines"][0]
    reserved = client.post(
        f"/api/v1/sales/orders/{order['id']}/lines/{line['id']}/reservations",
        headers=headers,
        json={"qty": "2.000"},
    )
    assert reserved.status_code == 200

    delivered = client.post(
        f"/api/v1/sales/orders/{order['id']}/deliveries",
        headers=headers,
        json={
            "doc_date": "2026-10-25",
            "lines": [{"order_line_id": line["id"], "qty": "3.000"}],
        },
    )
    assert delivered.status_code == 201
    current_order = client.get(f"/api/v1/sales/orders/{order['id']}", headers=headers).json()
    assert current_order["lines"][0]["qty_reserved"] == "0.000"
    assert current_order["lines"][0]["qty_delivered"] == "3.000"
    assert [item["status"] for item in current_order["lines"][0]["reservations"]] == [
        "CONSUMED",
        "CONSUMED",
    ]
    balance = db_session.get(StockBalance, (product.id, warehouse.id))
    assert balance is not None
    assert balance.qty_on_hand == Decimal("7.000")
    assert balance.qty_reserved == Decimal("0.000")


def test_delivery_rejects_order_overage_and_rolls_back_insufficient_stock(
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
            "lines": [{"product_id": product.id, "qty_ordered": "12.000", "unit_price": "5.00"}],
        },
    )
    order = created.json()
    line = order["lines"][0]

    insufficient = client.post(
        f"/api/v1/sales/orders/{order['id']}/deliveries",
        headers=headers,
        json={
            "doc_date": "2026-10-25",
            "lines": [{"order_line_id": line["id"], "qty": "11.000"}],
        },
    )
    assert insufficient.status_code == 409
    assert insufficient.json()["detail"] == "STOCK_INSUFFICIENT"
    assert db_session.scalar(select(func.count(SalesDelivery.id))) == 0
    assert db_session.scalar(select(func.count(StockTransaction.id))) == 1
    assert db_session.scalar(select(func.count(StockReservation.id))) == 0
    balance = db_session.get(StockBalance, (product.id, warehouse.id))
    assert balance is not None
    assert balance.qty_on_hand == Decimal("10.000")
    assert balance.qty_reserved == Decimal("0.000")

    over_order = client.post(
        f"/api/v1/sales/orders/{order['id']}/deliveries",
        headers=headers,
        json={
            "doc_date": "2026-10-25",
            "lines": [{"order_line_id": line["id"], "qty": "13.000"}],
        },
    )
    assert over_order.status_code == 409
    assert over_order.json()["detail"] == "DELIVERY_EXCEEDS_ORDER_REMAINING"
    assert db_session.scalar(select(func.count(SalesDelivery.id))) == 0


def test_invoice_posts_from_delivery_updates_due_and_preserves_cogs(
    client: TestClient,
    db_session: Session,
    sales_order_fixture: tuple[User, str, Customer, Warehouse, Product],
) -> None:
    actor, password, customer, warehouse, product = sales_order_fixture
    customer.credit_limit = Decimal("20.00")
    db_session.commit()
    headers = _login(client, actor.username, password)
    order_response = client.post(
        "/api/v1/sales/orders",
        headers=headers,
        json={
            **_payload(customer, warehouse, product),
            "discount": "1.00",
            "lines": [{"product_id": product.id, "qty_ordered": "5.000", "unit_price": "5.00"}],
        },
    )
    assert order_response.status_code == 201
    order = order_response.json()
    delivery_response = client.post(
        f"/api/v1/sales/orders/{order['id']}/deliveries",
        headers=headers,
        json={
            "doc_date": "2026-10-25",
            "lines": [{"order_line_id": order["lines"][0]["id"], "qty": "3.000"}],
        },
    )
    assert delivery_response.status_code == 201

    response = client.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "delivery_id": delivery_response.json()["id"],
            "doc_date": "2026-10-25",
            "due_date": "2026-11-05",
        },
    )

    assert response.status_code == 201
    result = response.json()
    invoice = result["invoice"]
    assert invoice["doc_no"] == "INV-20260001"
    assert invoice["status"] == "POSTED"
    assert invoice["subtotal"] == "15.00"
    assert invoice["discount"] == "0.60"
    assert invoice["total"] == "14.40"
    assert invoice["cogs_total"] == "7.50"
    assert invoice["lines"][0]["unit_cost_cogs"] == "2.5000"
    assert result["credit_limit_warning"] is False
    statement = client.get(f"/api/v1/customers/{customer.id}/statement", headers=headers)
    assert statement.json()["balance"] == "14.40"
    assert [item["type"] for item in statement.json()["entries"]] == [
        "OPENING_BALANCE",
        "INVOICE",
    ]

    second_delivery = client.post(
        f"/api/v1/sales/orders/{order['id']}/deliveries",
        headers=headers,
        json={
            "doc_date": "2026-10-26",
            "lines": [{"order_line_id": order["lines"][0]["id"], "qty": "2.000"}],
        },
    )
    second_invoice = client.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "delivery_id": second_delivery.json()["id"],
            "doc_date": "2026-10-26",
            "due_date": "2026-11-06",
        },
    )
    assert second_invoice.status_code == 201
    assert second_invoice.json()["invoice"]["discount"] == "0.40"
    assert second_invoice.json()["invoice"]["total"] == "9.60"
    updated_statement = client.get(
        f"/api/v1/customers/{customer.id}/statement", headers=headers
    )
    assert updated_statement.json()["balance"] == "24.00"


def test_invoice_credit_limit_warns_or_blocks_without_partial_writes(
    client: TestClient,
    db_session: Session,
    sales_order_fixture: tuple[User, str, Customer, Warehouse, Product],
) -> None:
    actor, password, customer, warehouse, product = sales_order_fixture
    customer.credit_limit = Decimal("10.00")
    db_session.add(CompanySetting(key="credit_limit_mode", value="WARN"))
    db_session.commit()
    headers = _login(client, actor.username, password)
    order_response = client.post(
        "/api/v1/sales/orders",
        headers=headers,
        json=_payload(customer, warehouse, product),
    )
    order = order_response.json()
    delivery_response = client.post(
        f"/api/v1/sales/orders/{order['id']}/deliveries",
        headers=headers,
        json={
            "doc_date": "2026-10-25",
            "lines": [{"order_line_id": order["lines"][0]["id"], "qty": "3.000"}],
        },
    )
    invoice_payload = {
        "delivery_id": delivery_response.json()["id"],
        "doc_date": "2026-10-25",
        "due_date": "2026-11-05",
    }
    warned = client.post("/api/v1/sales/invoices", headers=headers, json=invoice_payload)
    assert warned.status_code == 201
    assert warned.json()["credit_limit_warning"] is True

    db_session.get(CompanySetting, "credit_limit_mode").value = "BLOCK"
    next_order_response = client.post(
        "/api/v1/sales/orders",
        headers=headers,
        json=_payload(customer, warehouse, product),
    )
    next_order = next_order_response.json()
    next_delivery = client.post(
        f"/api/v1/sales/orders/{next_order['id']}/deliveries",
        headers=headers,
        json={
            "doc_date": "2026-10-25",
            "lines": [{"order_line_id": next_order["lines"][0]["id"], "qty": "3.000"}],
        },
    )
    blocked = client.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "delivery_id": next_delivery.json()["id"],
            "doc_date": "2026-10-25",
            "due_date": "2026-11-05",
        },
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "CREDIT_LIMIT_EXCEEDED"
    audit_count = db_session.scalar(
        select(func.count(AuditLog.id)).where(AuditLog.entity_type == "invoice")
    )
    assert audit_count == 1


def test_invoice_requires_permission_and_rejects_duplicate_delivery_invoice(
    client: TestClient,
    db_session: Session,
    sales_order_fixture: tuple[User, str, Customer, Warehouse, Product],
) -> None:
    actor, password, customer, warehouse, product = sales_order_fixture
    headers = _login(client, actor.username, password)
    order = client.post(
        "/api/v1/sales/orders",
        headers=headers,
        json=_payload(customer, warehouse, product),
    ).json()
    delivery = client.post(
        f"/api/v1/sales/orders/{order['id']}/deliveries",
        headers=headers,
        json={
            "doc_date": "2026-10-25",
            "lines": [{"order_line_id": order["lines"][0]["id"], "qty": "1.000"}],
        },
    ).json()
    payload = {
        "delivery_id": delivery["id"],
        "doc_date": "2026-10-25",
        "due_date": "2026-11-05",
    }
    readonly = User(
        username="sales_invoice_readonly",
        full_name="Sales Invoice Readonly",
        password_hash=hash_password("ReadOnly-Password-123"),
    )
    db_session.add(readonly)
    db_session.commit()
    denied = client.post(
        "/api/v1/sales/invoices",
        headers=_login(client, readonly.username, "ReadOnly-Password-123"),
        json=payload,
    )
    assert denied.status_code == 403

    posted = client.post("/api/v1/sales/invoices", headers=headers, json=payload)
    assert posted.status_code == 201
    duplicate = client.post("/api/v1/sales/invoices", headers=headers, json=payload)
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "DELIVERY_ALREADY_INVOICED"


def test_sales_return_reduces_customer_due_and_restocks_at_original_cogs(
    client: TestClient,
    db_session: Session,
    sales_order_fixture: tuple[User, str, Customer, Warehouse, Product],
) -> None:
    actor, password, customer, warehouse, product = sales_order_fixture
    headers = _login(client, actor.username, password)
    order_response = client.post(
        "/api/v1/sales/orders",
        headers=headers,
        json={
            **_payload(customer, warehouse, product),
            "discount": "2.00",
            "lines": [{"product_id": product.id, "qty_ordered": "2.000", "unit_price": "10.00"}],
        },
    )
    assert order_response.status_code == 201
    order = order_response.json()
    delivery_response = client.post(
        f"/api/v1/sales/orders/{order['id']}/deliveries",
        headers=headers,
        json={
            "doc_date": "2026-10-25",
            "lines": [{"order_line_id": order["lines"][0]["id"], "qty": "2.000"}],
        },
    )
    assert delivery_response.status_code == 201
    delivery = delivery_response.json()
    invoice_response = client.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "delivery_id": delivery["id"],
            "doc_date": "2026-10-25",
            "due_date": "2026-11-05",
        },
    )
    assert invoice_response.status_code == 201
    invoice = invoice_response.json()["invoice"]

    returned = client.post(
        "/api/v1/sales/returns",
        headers=headers,
        json={
            "doc_date": "2026-10-26",
            "invoice_id": invoice["id"],
            "lines": [{"invoice_line_id": invoice["lines"][0]["id"], "qty": "1.000"}],
        },
    )
    assert returned.status_code == 201
    sales_return = returned.json()
    assert sales_return["doc_no"] == "SR-20260001"
    assert sales_return["total"] == "9.00"
    assert sales_return["lines"][0]["unit_cost_cogs"] == "2.5000"

    statement = client.get(
        f"/api/v1/customers/{customer.id}/statement",
        headers=headers,
    )
    assert statement.status_code == 200
    assert statement.json()["balance"] == "9.00"
    assert [entry["type"] for entry in statement.json()["entries"]] == [
        "OPENING_BALANCE",
        "INVOICE",
        "SALES_RETURN",
    ]

    balance = db_session.scalar(
        select(StockBalance).where(
            StockBalance.product_id == product.id,
            StockBalance.warehouse_id == warehouse.id,
        )
    )
    assert balance is not None
    assert balance.qty_on_hand == Decimal("9.000")
    return_movement = db_session.scalar(
        select(StockTransaction).where(StockTransaction.movement_type == MovementType.SALE_RETURN)
    )
    assert return_movement is not None
    assert return_movement.qty_signed == Decimal("1.000")
    assert return_movement.unit_cost == Decimal("2.5000")
    assert db_session.scalar(
        select(func.count(AuditLog.id)).where(AuditLog.entity_type == "sales_return")
    ) == 1
    options = client.get("/api/v1/sales/returns/options", headers=headers)
    assert options.status_code == 200
    option_line = options.json()["invoices"][0]["lines"][0]
    assert option_line["qty_returned"] == "1.000"
    assert option_line["qty_available"] == "1.000"

    final_return = client.post(
        "/api/v1/sales/returns",
        headers=headers,
        json={
            "doc_date": "2026-10-27",
            "invoice_id": invoice["id"],
            "lines": [{"invoice_line_id": invoice["lines"][0]["id"], "qty": "1.000"}],
        },
    )
    assert final_return.status_code == 201
    assert final_return.json()["total"] == "9.00"
    updated_statement = client.get(
        f"/api/v1/customers/{customer.id}/statement",
        headers=headers,
    )
    assert updated_statement.json()["balance"] == "0.00"
    assert client.get("/api/v1/sales/returns/options", headers=headers).json()["invoices"] == []


def test_sales_return_requires_permission_and_caps_qty_at_delivered(
    client: TestClient,
    db_session: Session,
    sales_order_fixture: tuple[User, str, Customer, Warehouse, Product],
) -> None:
    actor, password, customer, warehouse, product = sales_order_fixture
    headers = _login(client, actor.username, password)
    order = client.post(
        "/api/v1/sales/orders",
        headers=headers,
        json={
            **_payload(customer, warehouse, product),
            "lines": [{"product_id": product.id, "qty_ordered": "2.000", "unit_price": "10.00"}],
        },
    ).json()
    delivery = client.post(
        f"/api/v1/sales/orders/{order['id']}/deliveries",
        headers=headers,
        json={
            "doc_date": "2026-10-25",
            "lines": [{"order_line_id": order["lines"][0]["id"], "qty": "1.000"}],
        },
    ).json()
    invoice = client.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "delivery_id": delivery["id"],
            "doc_date": "2026-10-25",
            "due_date": "2026-11-05",
        },
    ).json()["invoice"]
    payload = {
        "doc_date": "2026-10-26",
        "invoice_id": invoice["id"],
        "lines": [{"invoice_line_id": invoice["lines"][0]["id"], "qty": "2.000"}],
    }
    readonly = User(
        username="sales_return_readonly",
        full_name="Sales Return Readonly",
        password_hash=hash_password("ReadOnly-Password-123"),
    )
    db_session.add(readonly)
    db_session.commit()
    denied = client.post(
        "/api/v1/sales/returns",
        headers=_login(client, readonly.username, "ReadOnly-Password-123"),
        json=payload,
    )
    assert denied.status_code == 403

    excessive = client.post("/api/v1/sales/returns", headers=headers, json=payload)
    assert excessive.status_code == 409
    assert excessive.json()["detail"] == "SALES_RETURN_EXCEEDS_DELIVERED_QTY"
    assert db_session.scalar(
        select(func.count(StockTransaction.id)).where(
            StockTransaction.movement_type == MovementType.SALE_RETURN
        )
    ) == 0


def test_delivery_route_requires_permission(
    client: TestClient,
    db_session: Session,
    sales_order_fixture: tuple[User, str, Customer, Warehouse, Product],
) -> None:
    actor, password, customer, warehouse, product = sales_order_fixture
    created = client.post(
        "/api/v1/sales/orders",
        headers=_login(client, actor.username, password),
        json={
            **_payload(customer, warehouse, product),
            "lines": [{"product_id": product.id, "qty_ordered": "2.000", "unit_price": "5.00"}],
        },
    )
    order = created.json()
    line_id = order["lines"][0]["id"]
    readonly = User(
        username="sales_delivery_readonly",
        full_name="Sales Delivery Readonly",
        password_hash=hash_password("ReadOnly-Password-123"),
    )
    db_session.add(readonly)
    db_session.commit()
    response = client.post(
        f"/api/v1/sales/orders/{order['id']}/deliveries",
        headers=_login(client, readonly.username, "ReadOnly-Password-123"),
        json={
            "doc_date": "2026-10-25",
            "lines": [{"order_line_id": line_id, "qty": "1.000"}],
        },
    )
    assert response.status_code == 403
