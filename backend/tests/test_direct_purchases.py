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
from app.modules.direct_purchases.models import DirectPurchase
from app.modules.document_numbering.models import DocumentSequence
from app.modules.inventory.models import MovementType, StockBalance, StockTransaction
from app.modules.inventory.service import post_stock_movement
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
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def direct_purchase_fixture(
    db_session: Session,
) -> tuple[User, str, Supplier, Warehouse, Product]:
    result = seed_initial_admin(db_session)
    assert result.password is not None
    actor = db_session.scalar(select(User).where(User.username == result.username))
    assert actor is not None
    supplier = Supplier(
        code="SUP-DP", name="Direct Purchase Supplier", opening_due=Decimal("25.00")
    )
    warehouse = Warehouse(code="DP-MAIN", name="Direct Purchase Warehouse")
    category = ProductCategory(name="Direct Purchase Category")
    unit = Unit(name="Direct Purchase Unit", code="dpu", allow_decimal=True)
    db_session.add_all([supplier, warehouse, category, unit])
    db_session.flush()
    product = Product(
        sku="DP-RAW-001",
        name="Direct Purchase Product",
        type=ProductType.RAW,
        category_id=category.id,
        unit_id=unit.id,
        is_stocked=True,
        avg_cost=Decimal("2.0000"),
    )
    db_session.add(product)
    db_session.add(
        DocumentSequence(
            doc_type="DIRECT_PURCHASE",
            prefix="DP-",
            year=2026,
            last_number=0,
            padding=4,
        )
    )
    db_session.commit()
    return actor, result.password, supplier, warehouse, product


def _login(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def _payload(
    supplier: Supplier,
    warehouse: Warehouse,
    product: Product,
    *,
    qty: str = "4.000",
    unit_cost: str = "3.0000",
) -> dict[str, object]:
    return {
        "doc_date": "2026-10-16",
        "supplier_id": supplier.id,
        "warehouse_id": warehouse.id,
        "note": "Counter purchase",
        "lines": [{"product_id": product.id, "qty": qty, "unit_cost": unit_cost}],
    }


def test_direct_purchase_posts_stock_cost_due_and_audit_atomically(
    client: TestClient,
    db_session: Session,
    direct_purchase_fixture: tuple[User, str, Supplier, Warehouse, Product],
) -> None:
    actor, password, supplier, warehouse, product = direct_purchase_fixture
    headers = _login(client, actor.username, password)
    options = client.get("/api/v1/purchase/direct-purchases/options", headers=headers)
    assert options.status_code == 200
    assert options.json()["suppliers"][0]["id"] == supplier.id
    assert options.json()["warehouses"][0]["id"] == warehouse.id
    assert options.json()["products"][0]["id"] == product.id
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
        "/api/v1/purchase/direct-purchases",
        headers=headers,
        json=_payload(supplier, warehouse, product),
    )

    assert response.status_code == 201
    purchase = response.json()
    assert purchase["doc_no"] == "DP-20260001"
    assert purchase["status"] == "POSTED"
    assert purchase["total"] == "12.00"
    assert purchase["paid_amount"] == "0.00"
    assert purchase["money_account_id"] is None
    assert purchase["lines"][0]["product_sku"] == product.sku
    assert purchase["lines"][0]["line_total"] == "12.00"
    detail = client.get(
        f"/api/v1/purchase/direct-purchases/{purchase['id']}",
        headers=headers,
    )
    assert detail.status_code == 200
    assert detail.json()["doc_no"] == "DP-20260001"
    db_session.refresh(product)
    assert product.avg_cost == Decimal("2.4444")
    balance = db_session.get(StockBalance, (product.id, warehouse.id))
    assert balance is not None and balance.qty_on_hand == Decimal("9.000")
    movement = db_session.scalar(
        select(StockTransaction).where(
            StockTransaction.source_type == "DIRECT_PURCHASE",
            StockTransaction.source_id == purchase["id"],
        )
    )
    assert movement is not None
    assert movement.movement_type == MovementType.PURCHASE_RECEIPT
    assert movement.unit_cost == Decimal("3.0000")
    audit = db_session.scalar(
        select(AuditLog).where(
            AuditLog.entity_type == "direct_purchase",
            AuditLog.entity_id == str(purchase["id"]),
            AuditLog.action == "CREATE",
        )
    )
    assert audit is not None

    statement = client.get(f"/api/v1/suppliers/{supplier.id}/statement", headers=headers)
    assert statement.status_code == 200
    assert statement.json()["balance"] == "37.00"
    assert statement.json()["entries"][-1]["description"] == "Direct Purchase DP-20260001"


def test_direct_purchase_rejects_total_above_supported_money_amount(
    client: TestClient,
    db_session: Session,
    direct_purchase_fixture: tuple[User, str, Supplier, Warehouse, Product],
) -> None:
    actor, password, supplier, warehouse, product = direct_purchase_fixture
    headers = _login(client, actor.username, password)

    response = client.post(
        "/api/v1/purchase/direct-purchases",
        headers=headers,
        json=_payload(
            supplier,
            warehouse,
            product,
            qty="1000.000",
            unit_cost="99999999999999.9999",
        ),
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Direct purchase total exceeds supported amount"
    assert db_session.scalar(select(func.count(DirectPurchase.id))) == 0


def test_direct_purchase_failure_rolls_back_document_stock_and_numbering(
    client: TestClient,
    db_session: Session,
    direct_purchase_fixture: tuple[User, str, Supplier, Warehouse, Product],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor, password, supplier, warehouse, product = direct_purchase_fixture
    headers = _login(client, actor.username, password)
    import app.modules.direct_purchases.service as direct_purchase_service

    original_post_stock_movement = direct_purchase_service.post_stock_movement

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
        raise RuntimeError("Simulated failure after stock posting")

    monkeypatch.setattr(direct_purchase_service, "post_stock_movement", fail_after_stock_posting)
    response = client.post(
        "/api/v1/purchase/direct-purchases",
        headers=headers,
        json=_payload(supplier, warehouse, product),
    )

    assert response.status_code == 500
    assert db_session.scalar(select(func.count(DirectPurchase.id))) == 0
    assert (
        db_session.scalar(
            select(func.count(StockTransaction.id)).where(
                StockTransaction.source_type == "DIRECT_PURCHASE"
            )
        )
        == 0
    )
    assert db_session.scalar(select(func.count(StockBalance.product_id))) == 0
    sequence = db_session.scalar(
        select(DocumentSequence).where(DocumentSequence.doc_type == "DIRECT_PURCHASE")
    )
    assert sequence is not None and sequence.last_number == 0
    db_session.refresh(product)
    assert product.avg_cost == Decimal("2.0000")


def test_direct_purchase_endpoints_require_purchase_permissions(
    client: TestClient,
    db_session: Session,
) -> None:
    user = User(
        username="direct-purchase-reader-denied",
        full_name="Direct Purchase User Without Permission",
        password_hash=hash_password("Direct-Purchase-Test-Password-123"),
    )
    db_session.add(user)
    db_session.commit()
    headers = _login(client, user.username, "Direct-Purchase-Test-Password-123")

    options = client.get("/api/v1/purchase/direct-purchases/options", headers=headers)
    posting = client.post(
        "/api/v1/purchase/direct-purchases",
        headers=headers,
        json={
            "doc_date": "2026-10-16",
            "supplier_id": 1,
            "warehouse_id": 1,
            "lines": [{"product_id": 1, "qty": "1.000", "unit_cost": "1.0000"}],
        },
    )
    assert options.status_code == 403
    assert posting.status_code == 403
