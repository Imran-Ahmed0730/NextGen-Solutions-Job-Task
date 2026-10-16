from collections.abc import Generator

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
from app.modules.document_numbering.models import DocumentSequence
from app.modules.product_categories.models import ProductCategory
from app.modules.products.models import Product, ProductType
from app.modules.purchase_orders.models import PurchaseOrder
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
def purchase_order_fixture(
    db_session: Session,
) -> tuple[User, str, Supplier, Warehouse, Product]:
    result = seed_initial_admin(db_session)
    assert result.password is not None
    actor = db_session.scalar(select(User).where(User.username == result.username))
    assert actor is not None

    supplier = Supplier(code="SUP-001", name="Raw Material Supplier")
    category = ProductCategory(name="Raw Materials")
    unit = Unit(name="Kilogram", code="kg", allow_decimal=True)
    warehouse = Warehouse(name="Main Warehouse", code="MAIN")
    db_session.add_all([supplier, category, unit, warehouse])
    db_session.flush()
    product = Product(
        sku="RAW-001",
        name="Raw Material",
        type=ProductType.RAW,
        category_id=category.id,
        unit_id=unit.id,
        is_stocked=True,
    )
    non_stocked_product = Product(
        sku="SERVICE-001",
        name="Non-stocked Service",
        type=ProductType.RAW,
        category_id=category.id,
        unit_id=unit.id,
        is_stocked=False,
    )
    db_session.add_all([product, non_stocked_product])
    db_session.add(
        DocumentSequence(
            doc_type="PURCHASE_ORDER",
            prefix="PO-",
            year=2026,
            last_number=0,
            padding=4,
        )
    )
    db_session.commit()
    for record in [supplier, warehouse, product]:
        db_session.refresh(record)
    return actor, result.password, supplier, warehouse, product


def _login(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def _payload(
    supplier: Supplier,
    warehouse: Warehouse,
    product: Product,
) -> dict[str, object]:
    return {
        "doc_date": "2026-10-15",
        "supplier_id": supplier.id,
        "warehouse_id": warehouse.id,
        "expected_date": "2026-10-30",
        "discount": "1.00",
        "note": "October restock",
        "lines": [
            {"product_id": product.id, "qty": "3.250", "unit_price": "4.00"},
            {"product_id": product.id, "qty": "2.000", "unit_price": "2.50"},
        ],
    }


def test_purchase_order_draft_calculates_totals_and_can_be_updated(
    client: TestClient,
    db_session: Session,
    purchase_order_fixture: tuple[User, str, Supplier, Warehouse, Product],
) -> None:
    actor, password, supplier, warehouse, product = purchase_order_fixture
    headers = _login(client, actor.username, password)

    response = client.post(
        "/api/v1/purchase/orders",
        headers=headers,
        json=_payload(supplier, warehouse, product),
    )

    assert response.status_code == 201
    order = response.json()
    assert order["doc_no"] == "PO-20260001"
    assert order["status"] == "DRAFT"
    assert order["subtotal"] == "18.00"
    assert order["discount"] == "1.00"
    assert order["total"] == "17.00"
    assert [line["line_total"] for line in order["lines"]] == ["13.00", "5.00"]
    assert [line["received_qty"] for line in order["lines"]] == ["0.000", "0.000"]

    update_payload = _payload(supplier, warehouse, product)
    update_payload["discount"] = "0.00"
    update_payload["lines"] = [{"product_id": product.id, "qty": "4.000", "unit_price": "2.00"}]
    updated = client.put(
        f"/api/v1/purchase/orders/{order['id']}",
        headers=headers,
        json=update_payload,
    )

    assert updated.status_code == 200
    assert updated.json()["doc_no"] == "PO-20260001"
    assert updated.json()["subtotal"] == "8.00"
    assert updated.json()["total"] == "8.00"
    assert len(updated.json()["lines"]) == 1
    assert updated.json()["lines"][0]["qty"] == "4.000"
    assert (
        db_session.scalar(
            select(func.count(AuditLog.id)).where(AuditLog.entity_type == "purchase_order")
        )
        == 2
    )
    sequence = db_session.scalar(
        select(DocumentSequence).where(DocumentSequence.doc_type == "PURCHASE_ORDER")
    )
    assert sequence is not None
    assert sequence.last_number == 1

    listing = client.get("/api/v1/purchase/orders", headers=headers)
    detail = client.get(f"/api/v1/purchase/orders/{order['id']}", headers=headers)
    options = client.get("/api/v1/purchase/orders/options", headers=headers)
    assert listing.status_code == detail.status_code == options.status_code == 200
    assert listing.json()[0]["doc_no"] == "PO-20260001"
    assert detail.json()["id"] == order["id"]
    assert options.json()["suppliers"][0]["id"] == supplier.id
    assert options.json()["products"][0]["id"] == product.id
    assert len(options.json()["products"]) == 1


def test_purchase_order_rejects_invalid_lines_and_non_draft_updates(
    client: TestClient,
    db_session: Session,
    purchase_order_fixture: tuple[User, str, Supplier, Warehouse, Product],
) -> None:
    actor, password, supplier, warehouse, product = purchase_order_fixture
    headers = _login(client, actor.username, password)
    payload = _payload(supplier, warehouse, product)

    excessive_discount = dict(payload, discount="19.00")
    response = client.post("/api/v1/purchase/orders", headers=headers, json=excessive_discount)
    assert response.status_code == 422
    assert response.json()["detail"] == "Discount cannot exceed the subtotal"

    negative_qty = _payload(supplier, warehouse, product)
    negative_qty["lines"] = [{"product_id": product.id, "qty": "-1.000", "unit_price": "1.00"}]
    response = client.post("/api/v1/purchase/orders", headers=headers, json=negative_qty)
    assert response.status_code == 422

    non_stocked = _payload(supplier, warehouse, product)
    non_stocked["lines"] = [{"product_id": product.id + 1, "qty": "1.000", "unit_price": "1.00"}]
    response = client.post("/api/v1/purchase/orders", headers=headers, json=non_stocked)
    assert response.status_code == 422
    assert response.json()["detail"] == "Only stocked products can be ordered"
    assert db_session.scalar(select(func.count(PurchaseOrder.id))) == 0

    created = client.post("/api/v1/purchase/orders", headers=headers, json=payload)
    assert created.status_code == 201
    stored = db_session.get(PurchaseOrder, created.json()["id"])
    assert stored is not None
    changed_year = _payload(supplier, warehouse, product)
    changed_year["doc_date"] = "2027-01-01"
    rejected = client.put(
        f"/api/v1/purchase/orders/{stored.id}",
        headers=headers,
        json=changed_year,
    )
    assert rejected.status_code == 422
    assert rejected.json()["detail"] == "Document date year cannot change after numbering"

    stored.status = "APPROVED"
    db_session.commit()

    rejected = client.put(
        f"/api/v1/purchase/orders/{stored.id}",
        headers=headers,
        json=payload,
    )
    assert rejected.status_code == 409
    assert rejected.json()["detail"] == "PURCHASE_ORDER_NOT_EDITABLE"


def test_purchase_order_routes_require_permissions(
    client: TestClient,
    db_session: Session,
    purchase_order_fixture: tuple[User, str, Supplier, Warehouse, Product],
) -> None:
    _, _, supplier, warehouse, product = purchase_order_fixture
    assert client.get("/api/v1/purchase/orders").status_code == 401
    assert client.get("/api/v1/purchase/orders/options").status_code == 401

    readonly = User(
        username="purchase_readonly",
        full_name="Purchase Readonly",
        password_hash=hash_password("ReadOnly-Password-123"),
    )
    db_session.add(readonly)
    db_session.commit()
    headers = _login(client, readonly.username, "ReadOnly-Password-123")
    payload = _payload(supplier, warehouse, product)

    assert client.get("/api/v1/purchase/orders", headers=headers).status_code == 403
    assert client.get("/api/v1/purchase/orders/options", headers=headers).status_code == 403
    assert client.post("/api/v1/purchase/orders", headers=headers, json=payload).status_code == 403
    assert client.post("/api/v1/purchase/orders/1/submit", headers=headers).status_code == 403
    assert client.get("/api/v1/approvals/requests", headers=headers).status_code == 403
    assert client.post("/api/v1/purchase/orders/1/cancel", headers=headers).status_code == 403


def test_purchase_order_lifecycle_transitions(
    client: TestClient,
    db_session: Session,
    purchase_order_fixture: tuple[User, str, Supplier, Warehouse, Product],
) -> None:
    actor, password, supplier, warehouse, product = purchase_order_fixture
    headers = _login(client, actor.username, password)
    payload = _payload(supplier, warehouse, product)

    created = client.post("/api/v1/purchase/orders", headers=headers, json=payload)
    assert created.status_code == 201
    po_id = created.json()["id"]
    assert created.json()["status"] == "DRAFT"

    # No matching approval rule allows the order to proceed without an approval wait.
    submitted = client.post(f"/api/v1/purchase/orders/{po_id}/submit", headers=headers)
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "APPROVED"

    # Cannot submit again
    invalid_submit = client.post(f"/api/v1/purchase/orders/{po_id}/submit", headers=headers)
    assert invalid_submit.status_code == 409

    # Cancel approved PO
    cancelled = client.post(f"/api/v1/purchase/orders/{po_id}/cancel", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"

    # Cannot cancel again
    invalid_cancel = client.post(f"/api/v1/purchase/orders/{po_id}/cancel", headers=headers)
    assert invalid_cancel.status_code == 409
