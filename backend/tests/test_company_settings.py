from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.modules.auth.models import AuditLog, User
from app.modules.auth.seed import seed_initial_admin
from app.modules.company_settings.models import CompanySetting
from app.modules.company_settings.seed import seed_company_settings
from app.modules.company_settings.storage import DEFAULT_BRAND_ASSETS


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


def test_company_setting_key_value_crud_audit(
    client: TestClient, db_session: Session
) -> None:
    headers = _login_admin(client, db_session)

    created = client.post(
        "/api/v1/company-settings",
        headers=headers,
        json={"key": "company_name", "value": "Sabuj Pran"},
    )
    assert created.status_code == 201
    assert created.json() == {"key": "company_name", "value": "Sabuj Pran"}

    duplicate = client.post(
        "/api/v1/company-settings",
        headers=headers,
        json={"key": "company_name", "value": "Duplicate"},
    )
    assert duplicate.status_code == 409

    fetched = client.get("/api/v1/company-settings/company_name", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["value"] == "Sabuj Pran"

    updated = client.patch(
        "/api/v1/company-settings/company_name",
        headers=headers,
        json={"value": "Sabuj Pran Ltd"},
    )
    assert updated.status_code == 200
    assert updated.json()["value"] == "Sabuj Pran Ltd"

    listed = client.get("/api/v1/company-settings", headers=headers).json()
    assert any(item["key"] == "company_name" for item in listed)

    deleted = client.delete("/api/v1/company-settings/company_name", headers=headers)
    assert deleted.status_code == 204

    missing = client.get("/api/v1/company-settings/company_name", headers=headers)
    assert missing.status_code == 404

    audits = list(
        db_session.scalars(
            select(AuditLog).where(AuditLog.entity_type == "company_setting")
        )
    )
    actions = [entry.action for entry in audits]
    assert actions == ["CREATE", "UPDATE", "DELETE"]


def test_company_setting_permission_denial(
    client: TestClient, db_session: Session
) -> None:
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

    assert client.get("/api/v1/company-settings", headers=headers).status_code == 403
    assert client.get("/api/v1/company-settings/branding", headers=headers).status_code == 403
    assert (
        client.post(
            "/api/v1/company-settings",
            headers=headers,
            json={"key": "company_name", "value": "X"},
        ).status_code
        == 403
    )
    assert (
        client.patch(
            "/api/v1/company-settings/company_name",
            headers=headers,
            json={"value": "Y"},
        ).status_code
        == 403
    )
    assert (
        client.delete("/api/v1/company-settings/company_name", headers=headers).status_code == 403
    )
    assert (
        client.put(
            "/api/v1/company-settings/assets/logo",
            content=b"\x89PNG\r\n\x1a\n",
            headers={"Authorization": headers["Authorization"], "Content-Type": "image/png"},
        ).status_code
        == 403
    )


def test_company_setting_seed_is_idempotent_and_preserves_custom_values(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COMPANY_NAME", "Seeded Company")
    monkeypatch.setenv("CURRENCY_CODE", "BDT")

    inserted = seed_company_settings(db_session)
    db_session.commit()

    assert inserted == 11
    assert db_session.get(CompanySetting, "company_name").value == "Seeded Company"
    assert db_session.get(CompanySetting, "currency_code").value == "BDT"
    assert db_session.get(CompanySetting, "timezone").value == "Asia/Dhaka"
    assert (
        db_session.get(CompanySetting, "company_logo_path").value
        == DEFAULT_BRAND_ASSETS["logo"]
    )
    assert (
        db_session.get(CompanySetting, "company_favicon_path").value
        == DEFAULT_BRAND_ASSETS["favicon"]
    )
    assert db_session.get(CompanySetting, "invoice_footer") is not None

    db_session.get(CompanySetting, "company_name").value = "Custom Company"
    db_session.commit()

    assert seed_company_settings(db_session) == 0
    db_session.commit()
    assert db_session.get(CompanySetting, "company_name").value == "Custom Company"

    seed_company_settings(db_session, overwrite=True)
    db_session.commit()
    assert db_session.get(CompanySetting, "company_name").value == "Seeded Company"


def test_company_logo_and_favicon_upload(
    client: TestClient,
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modules.company_settings import router as settings_router

    headers = _login_admin(client, db_session)
    media_root = tmp_path / "company"
    monkeypatch.setattr(settings_router, "COMPANY_MEDIA_ROOT", media_root)
    png_data = b"\x89PNG\r\n\x1a\nvalid-test-image"

    logo = client.put(
        "/api/v1/company-settings/assets/logo",
        headers={**headers, "Content-Type": "image/png"},
        content=png_data,
    )
    assert logo.status_code == 200
    assert logo.json()["key"] == "company_logo_path"
    assert logo.json()["value"].startswith("/media/company/logo-")
    assert logo.json()["value"].endswith(".png")
    assert (media_root / logo.json()["value"].rsplit("/", maxsplit=1)[1]).read_bytes() == png_data

    favicon = client.put(
        "/api/v1/company-settings/assets/favicon",
        headers={**headers, "Content-Type": "image/png"},
        content=png_data,
    )
    assert favicon.status_code == 200
    assert favicon.json()["key"] == "company_favicon_path"
    assert favicon.json()["value"].startswith("/media/company/favicon-")

    invalid = client.put(
        "/api/v1/company-settings/assets/logo",
        headers={**headers, "Content-Type": "image/png"},
        content=b"not an image",
    )
    assert invalid.status_code == 415
    monkeypatch.setitem(settings_router.MAX_ASSET_SIZES, "logo", len(png_data))
    too_large = client.put(
        "/api/v1/company-settings/assets/logo",
        headers={**headers, "Content-Type": "image/png"},
        content=png_data + b"x",
    )
    assert too_large.status_code == 413


def test_authenticated_branding_endpoint_uses_seeded_defaults(
    client: TestClient, db_session: Session
) -> None:
    headers = _login_admin(client, db_session)
    response = client.get("/api/v1/company-settings/branding", headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "company_name": "Sabuj Pran",
        "company_logo_path": DEFAULT_BRAND_ASSETS["logo"],
        "company_favicon_path": DEFAULT_BRAND_ASSETS["favicon"],
    }


def test_company_setting_validation(
    client: TestClient, db_session: Session
) -> None:
    headers = _login_admin(client, db_session)

    invalid_settings = [
        ("company_name", " "),
        ("company_email", "not-an-email"),
        ("currency_code", "US"),
        ("timezone", "not a timezone"),
        ("credit_limit_mode", "ALLOW"),
        ("receipt_tolerance_pct", "-1"),
        ("receipt_tolerance_pct", "NaN"),
    ]
    for key, value in invalid_settings:
        response = client.put(
            f"/api/v1/company-settings/{key}",
            headers=headers,
            json={"value": value},
        )
        assert response.status_code == 422, key