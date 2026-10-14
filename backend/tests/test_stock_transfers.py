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
from app.modules.document_numbering.models import DocumentSequence
from app.modules.inventory.models import MovementType, StockBalance, StockTransaction
from app.modules.inventory.service import post_stock_movement
from app.modules.product_categories.models import ProductCategory
from app.modules.products.models import Product, ProductType
from app.modules.stock_transfers.models import StockTransfer
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
def transfer_fixture(db_session: Session) -> tuple[User, str, Product, Warehouse, Warehouse]:
    result = seed_initial_admin(db_session)
    assert result.password is not None
    actor = db_session.scalar(select(User).where(User.username == result.username))
    assert actor is not None

    category = ProductCategory(name="Raw Materials")
    unit = Unit(name="Kilogram", code="kg", allow_decimal=True)
    source = Warehouse(name="Main Warehouse", code="MAIN")
    destination = Warehouse(name="Remote Warehouse", code="REMOTE")
    db_session.add_all([category, unit, source, destination])
    db_session.flush()
    product = Product(
        sku="RAW-001",
        name="Raw Material",
        type=ProductType.RAW,
        category_id=category.id,
        unit_id=unit.id,
        is_stocked=True,
    )
    db_session.add(product)
    db_session.add(
        DocumentSequence(
            doc_type="STOCK_TRANSFER",
            prefix="TR-",
            year=2026,
            last_number=0,
            padding=4,
        )
    )
    db_session.commit()
    db_session.refresh(product)
    db_session.refresh(source)
    db_session.refresh(destination)
    return actor, result.password, product, source, destination


def _opening_balance(
    db: Session, actor: User, product: Product, warehouse: Warehouse, qty: Decimal
) -> None:
    post_stock_movement(
        db,
        product_id=product.id,
        warehouse_id=warehouse.id,
        movement_type=MovementType.OPENING,
        qty_signed=qty,
        actor=actor,
    )
    db.commit()


def _login(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_transfer_posts_both_ledger_sides_and_balances_atomically(
    client: TestClient,
    db_session: Session,
    transfer_fixture: tuple[User, str, Product, Warehouse, Warehouse],
) -> None:
    actor, password, product, source, destination = transfer_fixture
    _opening_balance(db_session, actor, product, source, Decimal("10.000"))
    headers = _login(client, actor.username, password)

    response = client.post(
        "/api/v1/inventory/transfers",
        headers=headers,
        json={
            "doc_date": "2026-10-14",
            "from_warehouse_id": source.id,
            "to_warehouse_id": destination.id,
            "lines": [{"product_id": product.id, "qty": "3.250"}],
            "note": "Rebalance stock",
        },
    )

    assert response.status_code == 201
    transfer = response.json()
    assert transfer["doc_no"] == "TR-20260001"
    assert transfer["status"] == "POSTED"
    assert transfer["lines"][0]["qty"] == "3.250"
    source_balance = db_session.get(StockBalance, (product.id, source.id))
    destination_balance = db_session.get(StockBalance, (product.id, destination.id))
    assert source_balance is not None
    assert destination_balance is not None
    assert source_balance.qty_on_hand == Decimal("6.750")
    assert destination_balance.qty_on_hand == Decimal("3.250")
    ledger = list(
        db_session.scalars(
            select(StockTransaction)
            .where(StockTransaction.source_type == "STOCK_TRANSFER")
            .order_by(StockTransaction.id)
        )
    )
    assert [(row.movement_type, row.qty_signed) for row in ledger] == [
        (MovementType.TRANSFER_OUT, Decimal("-3.250")),
        (MovementType.TRANSFER_IN, Decimal("3.250")),
    ]
    assert all(row.source_id == transfer["id"] for row in ledger)
    sequence = db_session.scalar(
        select(DocumentSequence).where(DocumentSequence.doc_type == "STOCK_TRANSFER")
    )
    assert sequence is not None
    assert sequence.last_number == 1
    assert (
        db_session.scalar(
            select(func.count(AuditLog.id)).where(AuditLog.entity_type == "stock_transfer")
        )
        == 1
    )
    transfers = client.get("/api/v1/inventory/transfers", headers=headers)
    options = client.get("/api/v1/inventory/transfers/options", headers=headers)
    transfer_detail = client.get(f"/api/v1/inventory/transfers/{transfer['id']}", headers=headers)
    assert transfers.status_code == 200
    assert transfers.json()[0]["doc_no"] == "TR-20260001"
    assert options.status_code == 200
    assert options.json()["products"][0]["sku"] == product.sku
    assert transfer_detail.status_code == 200
    assert transfer_detail.json()["id"] == transfer["id"]


def test_insufficient_transfer_rolls_back_document_sequence_and_both_ledger_sides(
    client: TestClient,
    db_session: Session,
    transfer_fixture: tuple[User, str, Product, Warehouse, Warehouse],
) -> None:
    actor, password, product, source, destination = transfer_fixture
    _opening_balance(db_session, actor, product, source, Decimal("2.000"))
    headers = _login(client, actor.username, password)

    response = client.post(
        "/api/v1/inventory/transfers",
        headers=headers,
        json={
            "doc_date": "2026-10-14",
            "from_warehouse_id": source.id,
            "to_warehouse_id": destination.id,
            "lines": [{"product_id": product.id, "qty": "3.000"}],
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "STOCK_INSUFFICIENT"
    assert db_session.scalar(select(func.count(StockTransaction.id))) == 1
    assert db_session.scalar(select(func.count(StockTransfer.id))) == 0
    sequence = db_session.scalar(
        select(DocumentSequence).where(DocumentSequence.doc_type == "STOCK_TRANSFER")
    )
    assert sequence is not None
    assert sequence.last_number == 0
    assert db_session.get(StockBalance, (product.id, source.id)).qty_on_hand == Decimal("2.000")
    assert db_session.get(StockBalance, (product.id, destination.id)) is None


def test_later_line_failure_rolls_back_all_earlier_line_postings(
    client: TestClient,
    db_session: Session,
    transfer_fixture: tuple[User, str, Product, Warehouse, Warehouse],
) -> None:
    actor, password, product, source, destination = transfer_fixture
    second_product = Product(
        sku="RAW-002",
        name="Second Raw Material",
        type=ProductType.RAW,
        category_id=product.category_id,
        unit_id=product.unit_id,
        is_stocked=True,
    )
    db_session.add(second_product)
    db_session.commit()
    db_session.refresh(second_product)
    _opening_balance(db_session, actor, product, source, Decimal("10.000"))
    _opening_balance(db_session, actor, second_product, source, Decimal("1.000"))
    headers = _login(client, actor.username, password)

    response = client.post(
        "/api/v1/inventory/transfers",
        headers=headers,
        json={
            "doc_date": "2026-10-14",
            "from_warehouse_id": source.id,
            "to_warehouse_id": destination.id,
            "lines": [
                {"product_id": product.id, "qty": "2.000"},
                {"product_id": second_product.id, "qty": "2.000"},
            ],
        },
    )

    assert response.status_code == 409
    assert (
        db_session.scalar(
            select(func.count(StockTransaction.id)).where(
                StockTransaction.source_type == "STOCK_TRANSFER"
            )
        )
        == 0
    )
    assert db_session.scalar(select(func.count(StockTransfer.id))) == 0
    assert db_session.get(StockBalance, (product.id, source.id)).qty_on_hand == Decimal("10.000")
    assert db_session.get(StockBalance, (product.id, destination.id)) is None
    sequence = db_session.scalar(
        select(DocumentSequence).where(DocumentSequence.doc_type == "STOCK_TRANSFER")
    )
    assert sequence is not None
    assert sequence.last_number == 0


def test_transfer_requires_permission_and_distinct_warehouses(
    client: TestClient,
    db_session: Session,
    transfer_fixture: tuple[User, str, Product, Warehouse, Warehouse],
) -> None:
    (
        actor,
        password,
        product,
        source,
        _,
    ) = transfer_fixture
    payload = {
        "doc_date": "2026-10-14",
        "from_warehouse_id": source.id,
        "to_warehouse_id": source.id,
        "lines": [{"product_id": product.id, "qty": "1.000"}],
    }
    assert client.post("/api/v1/inventory/transfers", json=payload).status_code == 401

    headers = _login(client, actor.username, password)
    assert (
        client.post("/api/v1/inventory/transfers", headers=headers, json=payload).status_code == 422
    )

    readonly = User(
        username="transfer_readonly",
        full_name="Transfer Readonly",
        password_hash=hash_password("ReadOnly-Password-123"),
    )
    db_session.add(readonly)
    db_session.commit()
    readonly_headers = _login(client, readonly.username, "ReadOnly-Password-123")
    valid_payload = {
        **payload,
        "to_warehouse_id": transfer_fixture[4].id,
    }
    assert client.get("/api/v1/inventory/transfers", headers=readonly_headers).status_code == 403
    assert (
        client.get("/api/v1/inventory/transfers/options", headers=readonly_headers).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/inventory/transfers",
            headers=readonly_headers,
            json=valid_payload,
        ).status_code
        == 403
    )


def test_transfer_rejects_duplicate_product_lines(
    client: TestClient,
    transfer_fixture: tuple[User, str, Product, Warehouse, Warehouse],
) -> None:
    actor, password, product, source, destination = transfer_fixture
    headers = _login(client, actor.username, password)

    response = client.post(
        "/api/v1/inventory/transfers",
        headers=headers,
        json={
            "doc_date": "2026-10-14",
            "from_warehouse_id": source.id,
            "to_warehouse_id": destination.id,
            "lines": [
                {"product_id": product.id, "qty": "1.000"},
                {"product_id": product.id, "qty": "2.000"},
            ],
        },
    )

    assert response.status_code == 422
