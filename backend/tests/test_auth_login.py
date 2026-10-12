from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.main import app
from app.modules.auth.models import User
from app.modules.auth.seed import PASSWORD_HASH


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


def test_admin_login_issues_jwt_token(db_session: Session) -> None:
    user = User(
        username="admin",
        full_name="System Administrator",
        password_hash=PASSWORD_HASH.hash("secret123"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    from app.core.database import get_db

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "secret123"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["token_type"] == "bearer"
        assert payload["access_token"]
        assert payload["expires_in"] > 0
    finally:
        app.dependency_overrides.clear()
