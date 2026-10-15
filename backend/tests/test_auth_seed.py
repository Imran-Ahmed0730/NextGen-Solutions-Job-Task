from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.modules.auth.models import Permission, Role, User
from app.modules.auth.seed import (
    ADMIN_PERMISSION_CATALOG,
    ADMIN_ROLE_NAME,
    PASSWORD_HASH,
    seed_initial_admin,
)


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        yield db
    engine.dispose()


def test_seed_creates_admin_and_grants_catalog_permissions(session: Session) -> None:
    result = seed_initial_admin(session)
    session.commit()

    admin = session.scalar(select(User).where(User.username == "admin"))
    role = session.scalar(select(Role).where(Role.name == ADMIN_ROLE_NAME))

    assert result.created
    assert result.password is not None
    assert admin is not None
    assert admin.full_name == "System Administrator"
    assert PASSWORD_HASH.verify(result.password, admin.password_hash)
    assert result.password != admin.password_hash
    assert role is not None
    assert role in admin.roles
    seeded_codes = {permission.code for permission in role.permissions}
    catalog_codes = {item.code for item in ADMIN_PERMISSION_CATALOG}
    expected_sales_codes = {
        "sales.quotations.read",
        "sales.quotations.create",
        "sales.quotations.update",
        "sales.orders.read",
        "sales.orders.create",
        "sales.orders.update",
        "sales.orders.reserve",
    }
    assert seeded_codes == catalog_codes
    assert expected_sales_codes <= catalog_codes


def test_seed_is_idempotent_and_does_not_reset_existing_password(session: Session) -> None:
    first = seed_initial_admin(session)
    session.commit()
    original_hash = session.scalar(select(User.password_hash).where(User.username == "admin"))

    second = seed_initial_admin(session)
    session.commit()
    current_hash = session.scalar(select(User.password_hash).where(User.username == "admin"))

    assert first.password is not None
    assert not second.created
    assert second.password is None
    assert current_hash == original_hash
    assert session.scalar(select(func.count()).select_from(Permission)) == len(
        ADMIN_PERMISSION_CATALOG
    )
