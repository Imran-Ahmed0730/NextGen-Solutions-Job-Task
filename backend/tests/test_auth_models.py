from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from app.core.database import Base
from app.modules.auth.models import (
    AuditLog,
    PasswordReset,
    Permission,
    RefreshToken,
    Role,
    User,
    role_permissions,
    user_roles,
)


def test_auth_models_register_expected_tables() -> None:
    assert {
        "users",
        "roles",
        "permissions",
        "user_roles",
        "role_permissions",
        "refresh_tokens",
        "password_resets",
        "audit_logs",
    } <= Base.metadata.tables.keys()


def test_auth_identifiers_use_mysql_unsigned_bigints() -> None:
    ddl = str(CreateTable(User.__table__).compile(dialect=mysql.dialect()))

    assert "BIGINT UNSIGNED NOT NULL AUTO_INCREMENT" in ddl


def test_auth_associations_use_composite_primary_keys() -> None:
    assert {column.name for column in user_roles.primary_key.columns} == {"user_id", "role_id"}
    assert {column.name for column in role_permissions.primary_key.columns} == {
        "role_id",
        "permission_id",
    }


def test_optional_user_contacts_and_token_lifecycles_are_represented() -> None:
    assert User.__table__.c.email.nullable
    assert User.__table__.c.mobile.nullable
    assert "token_hash" in RefreshToken.__table__.c
    assert "revoked_at" in RefreshToken.__table__.c
    assert "used_at" in PasswordReset.__table__.c
    assert "code" in Permission.__table__.c
    assert "name" in Role.__table__.c
    assert "is_active" in Role.__table__.c
    assert "before_json" in AuditLog.__table__.c
