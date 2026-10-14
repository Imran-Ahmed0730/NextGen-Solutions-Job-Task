from collections.abc import Generator
from datetime import datetime
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
from app.modules.inventory.models import MovementType, StockBalance, StockTransaction
from app.modules.product_categories.models import ProductCategory
from app.modules.products.models import Product, ProductType
from app.modules.purchase_orders.models import PurchaseOrder, PurchaseOrderLine
from app.modules.purchase_returns.models import PurchaseReturn
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


def _login(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


@pytest.fixture
def return_fixture(
    client: TestClient,
    db_session: Session,
) -> tuple[User, str, Supplier, Warehouse, Product, int, int]:
    result = seed_initial_admin(db_session)
    assert result.password is not None
    actor = db_session.scalar(select(User).where(User.username == result.username))
    assert actor is not None
    supplier = Supplier(code="SUP-PR", name="Return Supplier", opening_due=Decimal("25.00"))
    warehouse = Warehouse(code="PR-MAIN", name="Return Warehouse")
    category = ProductCategory(name="Return Category")
    unit = Unit(name="Return Unit", code="prunit", allow_decimal=True)
    db_session.add_all([supplier, warehouse, category, unit])
    db_session.flush()
    product = Product(
        sku="PR-RAW-001",
        name="Return Product",
        type=ProductType.RAW,
        category_id=category.id,
        unit_id=unit.id,
        is_stocked=True,
        avg_cost=Decimal("0.0000"),
    )
    db_session.add(product)
    db_session.flush()
    purchase_order = PurchaseOrder(
        doc_no="PO-PR-0001",
        doc_date=datetime(2026, 10, 17).date(),
        supplier_id=supplier.id,
        warehouse_id=warehouse.id,
        status="APPROVED",
        subtotal=Decimal("42.50"),
        discount=Decimal("0.00"),
        total=Decimal("42.50"),
        created_by=actor.id,
        lines=[
            PurchaseOrderLine(
                product_id=product.id,
                qty=Decimal("10.000"),
                unit_price=Decimal("4.25"),
                line_total=Decimal("42.50"),
                received_qty=Decimal("0.000"),
            )
        ],
    )
    db_session.add_all(
        [
            purchase_order,
            CompanySetting(key="receipt_tolerance_pct", value="0"),
            DocumentSequence(
                doc_type="GOODS_RECEIPT",
                prefix="GR-",
                year=2026,
                last_number=0,
                padding=4,
            ),
            DocumentSequence(
                doc_type="PURCHASE_RETURN",
                prefix="PR-",
                year=2026,
                last_number=0,
                padding=4,
            ),
        ]
    )
    db_session.commit()
    headers = _login(client, actor.username, result.password)
    receipt_response = client.post(
        "/api/v1/purchase/receipts",
        headers=headers,
        json={
            "doc_date": "2026-10-17",
            "po_id": purchase_order.id,
            "lines": [
                {
                    "po_line_id": purchase_order.lines[0].id,
                    "qty": "10.000",
                    "unit_cost": "4.2500",
                }
            ],
        },
    )
    assert receipt_response.status_code == 201
    receipt = receipt_response.json()
    return (
        actor,
        result.password,
        supplier,
        warehouse,
        product,
        receipt["id"],
        receipt["lines"][0]["id"],
    )


def _payload(receipt_id: int, receipt_line_id: int, qty: str) -> dict[str, object]:
    return {
        "doc_date": "2026-10-17",
        "receipt_id": receipt_id,
        "note": "Supplier return",
        "lines": [{"receipt_line_id": receipt_line_id, "qty": qty}],
    }


def test_purchase_return_reverses_original_cost_stock_and_supplier_due(
    client: TestClient,
    db_session: Session,
    return_fixture: tuple[User, str, Supplier, Warehouse, Product, int, int],
) -> None:
    actor, password, supplier, warehouse, product, receipt_id, receipt_line_id = return_fixture
    headers = _login(client, actor.username, password)

    options = client.get("/api/v1/purchase/returns/options", headers=headers)
    assert options.status_code == 200
    receipt_option = options.json()["receipts"][0]
    assert receipt_option["id"] == receipt_id
    assert receipt_option["lines"][0]["qty_available"] == "10.000"

    response = client.post(
        "/api/v1/purchase/returns",
        headers=headers,
        json=_payload(receipt_id, receipt_line_id, "3.000"),
    )

    assert response.status_code == 201
    purchase_return = response.json()
    assert purchase_return["doc_no"] == "PR-20260001"
    assert purchase_return["total"] == "12.75"
    assert purchase_return["lines"][0]["unit_cost"] == "4.2500"
    assert purchase_return["lines"][0]["line_total"] == "12.75"
    movement = db_session.scalar(
        select(StockTransaction).where(
            StockTransaction.source_type == "PURCHASE_RETURN",
            StockTransaction.source_id == purchase_return["id"],
        )
    )
    assert movement is not None
    assert movement.movement_type == MovementType.PURCHASE_RETURN
    assert movement.qty_signed == Decimal("-3.000")
    assert movement.unit_cost == Decimal("4.2500")
    balance = db_session.get(StockBalance, (product.id, warehouse.id))
    assert balance is not None and balance.qty_on_hand == Decimal("7.000")
    db_session.refresh(product)
    assert product.avg_cost == Decimal("4.2500")
    assert (
        db_session.scalar(
            select(AuditLog.id).where(
                AuditLog.entity_type == "purchase_return",
                AuditLog.action == "CREATE",
            )
        )
        is not None
    )

    statement = client.get(f"/api/v1/suppliers/{supplier.id}/statement", headers=headers)
    assert statement.status_code == 200
    assert statement.json()["balance"] == "54.75"
    assert [entry["type"] for entry in statement.json()["entries"]] == [
        "OPENING_BALANCE",
        "PURCHASE",
        "PURCHASE_RETURN",
    ]

    over_return = client.post(
        "/api/v1/purchase/returns",
        headers=headers,
        json=_payload(receipt_id, receipt_line_id, "7.001"),
    )
    assert over_return.status_code == 409
    assert over_return.json()["detail"] == "PURCHASE_RETURN_EXCEEDS_RECEIVED_QTY"

    final_return = client.post(
        "/api/v1/purchase/returns",
        headers=headers,
        json=_payload(receipt_id, receipt_line_id, "7.000"),
    )
    assert final_return.status_code == 201
    assert final_return.json()["total"] == "29.75"
    balance = db_session.get(StockBalance, (product.id, warehouse.id))
    assert balance is not None and balance.qty_on_hand == Decimal("0.000")
    statement = client.get(f"/api/v1/suppliers/{supplier.id}/statement", headers=headers)
    assert statement.json()["balance"] == "25.00"
    options = client.get("/api/v1/purchase/returns/options", headers=headers)
    assert options.json()["receipts"] == []


def test_purchase_return_failure_rolls_back_stock_due_and_numbering(
    client: TestClient,
    db_session: Session,
    return_fixture: tuple[User, str, Supplier, Warehouse, Product, int, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor, password, supplier, warehouse, product, receipt_id, receipt_line_id = return_fixture
    headers = _login(client, actor.username, password)
    import app.modules.purchase_returns.service as purchase_return_service

    original_post_stock_movement = purchase_return_service.post_stock_movement

    def fail_after_stock_posting(
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
        original_post_stock_movement(
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
        raise RuntimeError("Simulated failure after stock return")

    monkeypatch.setattr(purchase_return_service, "post_stock_movement", fail_after_stock_posting)
    response = client.post(
        "/api/v1/purchase/returns",
        headers=headers,
        json=_payload(receipt_id, receipt_line_id, "3.000"),
    )

    assert response.status_code == 500
    assert db_session.scalar(select(func.count(PurchaseReturn.id))) == 0
    assert (
        db_session.scalar(
            select(func.count(StockTransaction.id)).where(
                StockTransaction.source_type == "PURCHASE_RETURN"
            )
        )
        == 0
    )
    balance = db_session.get(StockBalance, (product.id, warehouse.id))
    assert balance is not None and balance.qty_on_hand == Decimal("10.000")
    sequence = db_session.scalar(
        select(DocumentSequence).where(DocumentSequence.doc_type == "PURCHASE_RETURN")
    )
    assert sequence is not None and sequence.last_number == 0
    statement = client.get(f"/api/v1/suppliers/{supplier.id}/statement", headers=headers)
    assert statement.json()["balance"] == "67.50"


def test_purchase_return_endpoints_require_purchase_permissions(
    client: TestClient,
    db_session: Session,
) -> None:
    user = User(
        username="purchase-return-reader-denied",
        full_name="Purchase Return User Without Permission",
        password_hash=hash_password("Purchase-Return-Test-Password-123"),
    )
    db_session.add(user)
    db_session.commit()
    headers = _login(client, user.username, "Purchase-Return-Test-Password-123")

    options = client.get("/api/v1/purchase/returns/options", headers=headers)
    posting = client.post(
        "/api/v1/purchase/returns",
        headers=headers,
        json={
            "doc_date": "2026-10-17",
            "receipt_id": 1,
            "lines": [{"receipt_line_id": 1, "qty": "1.000"}],
        },
    )
    assert options.status_code == 403
    assert posting.status_code == 403
