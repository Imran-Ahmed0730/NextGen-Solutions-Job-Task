from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.modules.auth.models import AuditLog, Permission, Role, User
from app.modules.customers.models import Customer
from app.modules.document_numbering.models import DocumentSequence
from app.modules.product_categories.models import ProductCategory
from app.modules.products.models import Product, ProductType
from app.modules.quotations.models import Quotation
from app.modules.units.models import Unit


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
def quotation_fixture(db_session: Session) -> tuple[User, str, Customer, Product]:
    from app.modules.auth.seed import seed_initial_admin

    result = seed_initial_admin(db_session)
    assert result.password is not None
    actor = db_session.scalar(select(User).where(User.username == result.username))
    assert actor is not None
    admin_role = db_session.scalar(select(Role).where(Role.name == "Administrator"))
    assert admin_role is not None
    quotation_permissions = [
        Permission(code=code, module="sales", description=code)
        for code in (
            "sales.quotations.read",
            "sales.quotations.create",
            "sales.quotations.update",
        )
    ]
    db_session.add_all(quotation_permissions)
    admin_role.permissions.extend(quotation_permissions)

    customer = Customer(code="CUS-001", name="Quotation Customer")
    category = ProductCategory(name="Quotation Products")
    unit = Unit(name="Piece", code="pcs", allow_decimal=True)
    db_session.add_all([customer, category, unit])
    db_session.flush()
    product = Product(
        sku="QUOTE-001",
        name="Quotation Product",
        type=ProductType.FINISHED,
        category_id=category.id,
        unit_id=unit.id,
        is_stocked=True,
    )
    db_session.add_all(
        [
            product,
            DocumentSequence(
                doc_type="QUOTATION",
                prefix="QT-",
                year=2026,
                last_number=0,
                padding=4,
            ),
        ]
    )
    db_session.commit()
    db_session.refresh(customer)
    db_session.refresh(product)
    return actor, result.password, customer, product


def _payload(customer: Customer, product: Product) -> dict[str, object]:
    return {
        "doc_date": "2026-10-23",
        "customer_id": customer.id,
        "valid_until": "2026-11-23",
        "discount": "1.00",
        "note": "Offer for October",
        "lines": [
            {"product_id": product.id, "qty": "3.250", "unit_price": "4.00"},
            {"product_id": product.id, "qty": "2.000", "unit_price": "2.50"},
        ],
    }


def test_quotation_draft_create_update_and_list(
    client: TestClient,
    db_session: Session,
    quotation_fixture: tuple[User, str, Customer, Product],
) -> None:
    actor, password, customer, product = quotation_fixture
    headers = _login(client, actor.username, password)

    created = client.post(
        "/api/v1/sales/quotations",
        headers=headers,
        json=_payload(customer, product),
    )
    assert created.status_code == 201
    quotation = created.json()
    assert quotation["doc_no"] == "QT-20260001"
    assert quotation["status"] == "DRAFT"
    assert quotation["subtotal"] == "18.00"
    assert quotation["discount"] == "1.00"
    assert quotation["total"] == "17.00"
    assert [line["line_total"] for line in quotation["lines"]] == ["13.00", "5.00"]

    changed = _payload(customer, product)
    changed["discount"] = "0.00"
    changed["lines"] = [{"product_id": product.id, "qty": "4.000", "unit_price": "2.00"}]
    updated = client.put(
        f"/api/v1/sales/quotations/{quotation['id']}",
        headers=headers,
        json=changed,
    )
    assert updated.status_code == 200
    assert updated.json()["doc_no"] == "QT-20260001"
    assert updated.json()["total"] == "8.00"
    assert len(updated.json()["lines"]) == 1

    listing = client.get("/api/v1/sales/quotations", headers=headers)
    detail = client.get(f"/api/v1/sales/quotations/{quotation['id']}", headers=headers)
    options = client.get("/api/v1/sales/quotations/options", headers=headers)
    assert listing.status_code == detail.status_code == options.status_code == 200
    assert listing.json()[0]["doc_no"] == "QT-20260001"
    assert detail.json()["id"] == quotation["id"]
    assert options.json()["customers"][0]["id"] == customer.id
    assert options.json()["products"][0]["id"] == product.id
    assert (
        db_session.scalar(
            select(func.count(AuditLog.id)).where(AuditLog.entity_type == "quotation")
        )
        == 2
    )
    assert db_session.scalar(select(func.count(Quotation.id))) == 1


def test_quotation_rejects_excessive_discount_and_invalid_product(
    client: TestClient,
    db_session: Session,
    quotation_fixture: tuple[User, str, Customer, Product],
) -> None:
    actor, password, customer, product = quotation_fixture
    headers = _login(client, actor.username, password)

    excessive_discount = _payload(customer, product)
    excessive_discount["discount"] = "19.00"
    response = client.post(
        "/api/v1/sales/quotations",
        headers=headers,
        json=excessive_discount,
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Discount cannot exceed the subtotal"

    invalid_product = _payload(customer, product)
    invalid_product["lines"] = [
        {"product_id": product.id + 1, "qty": "1.000", "unit_price": "1.00"}
    ]
    response = client.post(
        "/api/v1/sales/quotations",
        headers=headers,
        json=invalid_product,
    )
    assert response.status_code == 404

    whole_number_unit = Unit(name="Whole Piece", code="whole-pc", allow_decimal=False)
    db_session.add(whole_number_unit)
    db_session.flush()
    whole_product = Product(
        sku="QUOTE-WHOLE",
        name="Whole Piece Product",
        type=ProductType.FINISHED,
        category_id=product.category_id,
        unit_id=whole_number_unit.id,
        is_stocked=True,
    )
    db_session.add(whole_product)
    db_session.commit()
    invalid_fraction = _payload(customer, product)
    invalid_fraction["lines"] = [
        {"product_id": whole_product.id, "qty": "1.500", "unit_price": "1.00"}
    ]
    response = client.post(
        "/api/v1/sales/quotations",
        headers=headers,
        json=invalid_fraction,
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Product unit does not allow decimal quantity"

    oversized_total = _payload(customer, product)
    oversized_total["lines"] = [
        {
            "product_id": product.id,
            "qty": "999999999999999.999",
            "unit_price": "9999999999999999.99",
        }
    ]
    response = client.post(
        "/api/v1/sales/quotations",
        headers=headers,
        json=oversized_total,
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Quotation total exceeds supported amount"
    assert db_session.scalar(select(func.count(Quotation.id))) == 0


def test_quotation_routes_require_permissions(
    client: TestClient,
    db_session: Session,
    quotation_fixture: tuple[User, str, Customer, Product],
) -> None:
    _, _, customer, product = quotation_fixture
    assert client.get("/api/v1/sales/quotations").status_code == 401
    assert client.get("/api/v1/sales/quotations/options").status_code == 401

    readonly = User(
        username="quotation_readonly",
        full_name="Quotation Readonly",
        password_hash=hash_password("ReadOnly-Password-123"),
    )
    db_session.add(readonly)
    db_session.commit()
    headers = _login(client, readonly.username, "ReadOnly-Password-123")
    payload = _payload(customer, product)
    assert client.get("/api/v1/sales/quotations", headers=headers).status_code == 403
    assert client.get("/api/v1/sales/quotations/options", headers=headers).status_code == 403
    assert client.post("/api/v1/sales/quotations", headers=headers, json=payload).status_code == 403
