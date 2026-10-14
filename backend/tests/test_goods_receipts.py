from collections.abc import Generator
from datetime import date, datetime
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
from app.modules.document_numbering.models import DocumentSequence
from app.modules.goods_receipts.models import GoodsReceipt
from app.modules.inventory.models import MovementType, StockBalance, StockTransaction
from app.modules.inventory.service import post_stock_movement
from app.modules.product_categories.models import ProductCategory
from app.modules.products.models import Product, ProductType
from app.modules.purchase_orders.models import PurchaseOrder, PurchaseOrderLine
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
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def receipt_fixture(
    db_session: Session,
) -> tuple[User, str, Supplier, Warehouse, list[Product], PurchaseOrder]:
    result = seed_initial_admin(db_session)
    assert result.password is not None
    actor = db_session.scalar(select(User).where(User.username == result.username))
    assert actor is not None
    supplier = Supplier(code="SUP-GR", name="Receipt Supplier", opening_due=Decimal("25.00"))
    warehouse = Warehouse(code="GR-MAIN", name="Receipt Warehouse")
    category = ProductCategory(name="Receipt Category")
    unit = Unit(name="Receipt Unit", code="grunit", allow_decimal=True)
    db_session.add_all([supplier, warehouse, category, unit])
    db_session.flush()
    products = [
        Product(
            sku=f"GR-RAW-{index}",
            name=f"Receipt Product {index}",
            type=ProductType.RAW,
            category_id=category.id,
            unit_id=unit.id,
            is_stocked=True,
            avg_cost=Decimal("2.0000"),
        )
        for index in range(1, 3)
    ]
    db_session.add_all(products)
    db_session.flush()
    purchase_order = PurchaseOrder(
        doc_no="PO-GR-0001",
        doc_date=date(2026, 10, 15),
        supplier_id=supplier.id,
        warehouse_id=warehouse.id,
        status="APPROVED",
        subtotal=Decimal("100.00"),
        discount=Decimal("0.00"),
        total=Decimal("100.00"),
        created_by=actor.id,
        lines=[
            PurchaseOrderLine(
                product_id=products[0].id,
                qty=Decimal("10.000"),
                unit_price=Decimal("10.00"),
                line_total=Decimal("100.00"),
                received_qty=Decimal("0.000"),
            )
        ],
    )
    db_session.add_all(
        [
            purchase_order,
            CompanySetting(key="receipt_tolerance_pct", value="5"),
            DocumentSequence(
                doc_type="GOODS_RECEIPT",
                prefix="GR-",
                year=2026,
                last_number=0,
                padding=4,
            ),
        ]
    )
    db_session.commit()
    db_session.refresh(purchase_order)
    return actor, result.password, supplier, warehouse, products, purchase_order


def _login(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def _payload(po: PurchaseOrder, qty: str = "4.000", unit_cost: str = "3.0000") -> dict[str, object]:
    return {
        "doc_date": "2026-10-15",
        "po_id": po.id,
        "note": "First delivery",
        "lines": [{"po_line_id": po.lines[0].id, "qty": qty, "unit_cost": unit_cost}],
    }


def test_receipt_posts_stock_cost_and_supplier_due_atomically(
    client: TestClient,
    db_session: Session,
    receipt_fixture: tuple[User, str, Supplier, Warehouse, list[Product], PurchaseOrder],
) -> None:
    actor, password, supplier, warehouse, products, purchase_order = receipt_fixture
    headers = _login(client, actor.username, password)
    product = products[0]
    post_stock_movement(
        db_session,
        product_id=product.id,
        warehouse_id=warehouse.id,
        movement_type=MovementType.OPENING,
        qty_signed=Decimal("5.000"),
        unit_cost=Decimal("2.0000"),
        actor=actor,
    )
    db_session.commit()

    response = client.post(
        "/api/v1/purchase/receipts",
        headers=headers,
        json=_payload(purchase_order),
    )

    assert response.status_code == 201
    receipt = response.json()
    assert receipt["doc_no"] == "GR-20260001"
    assert receipt["status"] == "POSTED"
    assert receipt["total"] == "12.00"
    assert receipt["lines"][0]["line_total"] == "12.00"
    assert receipt["lines"][0]["product_sku"] == product.sku
    assert receipt["lines"][0]["product_name"] == product.name
    db_session.refresh(product)
    db_session.refresh(purchase_order)
    assert product.avg_cost == Decimal("2.4444")
    assert purchase_order.status == "PARTIALLY_RECEIVED"
    assert purchase_order.lines[0].received_qty == Decimal("4.000")
    balance = db_session.get(StockBalance, (product.id, warehouse.id))
    assert balance is not None
    assert balance.qty_on_hand == Decimal("9.000")
    receipt_movement = db_session.scalar(
        select(StockTransaction).where(
            StockTransaction.source_type == "GOODS_RECEIPT",
            StockTransaction.source_id == receipt["id"],
        )
    )
    assert receipt_movement is not None
    assert receipt_movement.movement_type == MovementType.PURCHASE_RECEIPT
    assert receipt_movement.unit_cost == Decimal("3.0000")
    audit_count = db_session.scalar(
        select(func.count(AuditLog.id)).where(
            AuditLog.entity_type.in_(["goods_receipt", "purchase_order", "stock_transaction"])
        )
    )
    assert audit_count is not None and audit_count >= 3
    statement = client.get(f"/api/v1/suppliers/{supplier.id}/statement", headers=headers)
    assert statement.status_code == 200
    assert statement.json()["balance"] == "37.00"
    assert [entry["type"] for entry in statement.json()["entries"]] == [
        "OPENING_BALANCE",
        "PURCHASE",
    ]


def test_receipt_requires_approved_po_and_respects_configured_tolerance(
    client: TestClient,
    db_session: Session,
    receipt_fixture: tuple[User, str, Supplier, Warehouse, list[Product], PurchaseOrder],
) -> None:
    actor, password, _, _, _, purchase_order = receipt_fixture
    headers = _login(client, actor.username, password)

    purchase_order.status = "DRAFT"
    db_session.commit()
    denied = client.post(
        "/api/v1/purchase/receipts",
        headers=headers,
        json=_payload(purchase_order, qty="1.000"),
    )
    assert denied.status_code == 409
    assert denied.json()["detail"] == "PURCHASE_ORDER_NOT_RECEIVABLE"
    purchase_order.status = "APPROVED"
    db_session.commit()

    too_much = client.post(
        "/api/v1/purchase/receipts",
        headers=headers,
        json=_payload(purchase_order, qty="10.501"),
    )
    assert too_much.status_code == 409
    assert too_much.json()["detail"] == "RECEIPT_EXCEEDS_ORDER_TOLERANCE"
    assert db_session.scalar(select(func.count(GoodsReceipt.id))) == 0

    allowed = client.post(
        "/api/v1/purchase/receipts",
        headers=headers,
        json=_payload(purchase_order, qty="10.500"),
    )
    assert allowed.status_code == 201
    db_session.refresh(purchase_order)
    assert purchase_order.status == "RECEIVED"
    assert purchase_order.lines[0].received_qty == Decimal("10.500")

    after_receipt = client.post(
        "/api/v1/purchase/receipts",
        headers=headers,
        json=_payload(purchase_order, qty="0.001"),
    )
    assert after_receipt.status_code == 409
    assert after_receipt.json()["detail"] == "PURCHASE_ORDER_NOT_RECEIVABLE"


def test_receipt_rejects_total_above_supported_money_amount(
    client: TestClient,
    db_session: Session,
    receipt_fixture: tuple[User, str, Supplier, Warehouse, list[Product], PurchaseOrder],
) -> None:
    actor, password, _, _, _, purchase_order = receipt_fixture
    headers = _login(client, actor.username, password)
    purchase_order.lines[0].qty = Decimal("1000.000")
    db_session.commit()

    response = client.post(
        "/api/v1/purchase/receipts",
        headers=headers,
        json=_payload(
            purchase_order,
            qty="1000.000",
            unit_cost="99999999999999.9999",
        ),
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Goods receipt total exceeds supported amount"
    assert db_session.scalar(select(func.count(GoodsReceipt.id))) == 0


def test_receipt_failure_rolls_back_document_stock_cost_and_sequence(
    client: TestClient,
    db_session: Session,
    receipt_fixture: tuple[User, str, Supplier, Warehouse, list[Product], PurchaseOrder],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor, password, _, _, products, purchase_order = receipt_fixture
    headers = _login(client, actor.username, password)
    import app.modules.goods_receipts.service as receipt_service

    original_post_stock_movement = receipt_service.post_stock_movement
    call_count = 0

    def fail_on_second_line(
        db: Session,
        *,
        product_id: int,
        warehouse_id: int,
        movement_type: MovementType,
        qty_signed: Decimal,
        actor: User,
        unit_cost: Decimal | None = None,
        source_type: str | None = None,
        source_id: int | None = None,
        source_line_id: int | None = None,
        note: str | None = None,
        txn_date: datetime | None = None,
    ) -> StockTransaction:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("Simulated stock posting failure")
        return original_post_stock_movement(
            db,
            product_id=product_id,
            warehouse_id=warehouse_id,
            movement_type=movement_type,
            qty_signed=qty_signed,
            actor=actor,
            unit_cost=unit_cost,
            source_type=source_type,
            source_id=source_id,
            source_line_id=source_line_id,
            note=note,
            txn_date=txn_date,
        )

    monkeypatch.setattr(receipt_service, "post_stock_movement", fail_on_second_line)
    payload = _payload(purchase_order)
    second_line = PurchaseOrderLine(
        product_id=products[1].id,
        qty=Decimal("10.000"),
        unit_price=Decimal("10.00"),
        line_total=Decimal("100.00"),
        received_qty=Decimal("0.000"),
    )
    purchase_order.lines.append(second_line)
    db_session.commit()
    payload["lines"] = [
        {"po_line_id": line.id, "qty": "1.000", "unit_cost": "3.0000"}
        for line in purchase_order.lines
    ]
    response = client.post("/api/v1/purchase/receipts", headers=headers, json=payload)
    assert response.status_code == 500

    assert db_session.scalar(select(func.count(GoodsReceipt.id))) == 0
    assert (
        db_session.scalar(
            select(func.count(StockTransaction.id)).where(
                StockTransaction.source_type == "GOODS_RECEIPT"
            )
        )
        == 0
    )
    assert db_session.scalar(select(func.count(StockBalance.product_id))) == 0
    sequence = db_session.scalar(
        select(DocumentSequence).where(DocumentSequence.doc_type == "GOODS_RECEIPT")
    )
    assert sequence is not None
    assert sequence.last_number == 0
    db_session.refresh(purchase_order)
    assert purchase_order.status == "APPROVED"
    assert all(line.received_qty == Decimal("0.000") for line in purchase_order.lines)
    for product in products:
        db_session.refresh(product)
        assert product.avg_cost == Decimal("2.0000")


def test_receipt_endpoints_require_purchase_receipt_permissions(
    client: TestClient,
    db_session: Session,
) -> None:
    user = User(
        username="receipt-reader-denied",
        full_name="Receipt Reader Without Permission",
        password_hash=hash_password("Receipt-Test-Password-123"),
    )
    db_session.add(user)
    db_session.commit()
    headers = _login(client, user.username, "Receipt-Test-Password-123")

    options = client.get("/api/v1/purchase/receipts/options", headers=headers)
    posting = client.post(
        "/api/v1/purchase/receipts",
        headers=headers,
        json={
            "doc_date": "2026-10-15",
            "po_id": 1,
            "lines": [{"po_line_id": 1, "qty": "1.000", "unit_cost": "1.0000"}],
        },
    )
    assert options.status_code == 403
    assert posting.status_code == 403
