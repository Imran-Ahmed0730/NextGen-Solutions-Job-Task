from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.modules.auth.models import User
from app.modules.auth.seed import seed_initial_admin
from app.modules.document_numbering.service import generate_next_number


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


def _login_admin(client: TestClient, db: Session) -> dict[str, str]:
    result = seed_initial_admin(db)
    db.commit()
    assert result.password is not None
    response = client.post(
        "/api/v1/auth/login",
        json={"username": result.username, "password": result.password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_document_sequence_crud_and_gap_free_numbering(
    client: TestClient, db_session: Session
) -> None:
    headers = _login_admin(client, db_session)

    created = client.post(
        "/api/v1/document-numbering",
        headers=headers,
        json={
            "doc_type": "INVOICE",
            "prefix": "INV-",
            "year": 2026,
            "last_number": 0,
            "padding": 4,
        },
    )
    assert created.status_code == 201
    sequence_id = created.json()["id"]
    assert created.json()["doc_type"] == "INVOICE"

    duplicate = client.post(
        "/api/v1/document-numbering",
        headers=headers,
        json={
            "doc_type": "INVOICE",
            "prefix": "INV-",
            "year": 2026,
            "last_number": 0,
            "padding": 4,
        },
    )
    assert duplicate.status_code == 409

    generated = [generate_next_number(db_session, "INVOICE", 2026) for _ in range(3)]
    db_session.commit()
    assert generated == ["INV-20260001", "INV-20260002", "INV-20260003"]

    updated = client.patch(
        f"/api/v1/document-numbering/{sequence_id}",
        headers=headers,
        json={"last_number": 10, "padding": 3},
    )
    assert updated.status_code == 200
    assert updated.json()["last_number"] == 10

    preview = client.get("/api/v1/document-numbering/INVOICE/next?year=2026", headers=headers)
    assert preview.status_code == 200
    assert preview.json()["number"] == "INV-2026011"

    deleted = client.delete(f"/api/v1/document-numbering/{sequence_id}", headers=headers)
    assert deleted.status_code == 204
    missing = client.get(f"/api/v1/document-numbering/{sequence_id}", headers=headers)
    assert missing.status_code == 404


def test_document_numbering_permission_denial(client: TestClient, db_session: Session) -> None:
    user = User(
        username="readonly",
        full_name="Read Only",
        password_hash=hash_password("ReadOnly-Password-123"),
    )
    db_session.add(user)
    db_session.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "readonly", "password": "ReadOnly-Password-123"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert client.get("/api/v1/document-numbering", headers=headers).status_code == 403
    assert (
        client.post(
            "/api/v1/document-numbering",
            headers=headers,
            json={"doc_type": "INVOICE", "prefix": "INV-", "year": 2026},
        ).status_code
        == 403
    )
