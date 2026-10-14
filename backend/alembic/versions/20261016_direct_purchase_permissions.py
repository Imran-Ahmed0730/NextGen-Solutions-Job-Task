"""Add Direct Purchase permissions."""

import sqlalchemy as sa

from alembic import op

revision = "20261016_dp_permissions"
down_revision = "20261016_direct_purchases"
branch_labels = None
depends_on = None

PERMISSIONS = (
    ("purchase.direct_purchases.read", "View direct purchases"),
    ("purchase.direct_purchases.create", "Post direct purchases"),
)


def upgrade() -> None:
    for code, description in PERMISSIONS:
        op.execute(
            sa.text(
                "INSERT INTO permissions (code, module, description) "
                "SELECT :code, 'purchase', :description "
                "WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = :code)"
            ).bindparams(code=code, description=description)
        )
    for code, _ in PERMISSIONS:
        op.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id, permission_id) "
                "SELECT roles.id, permissions.id FROM roles "
                "JOIN permissions ON permissions.code = :code "
                "WHERE roles.name = 'Administrator' "
                "AND NOT EXISTS (SELECT 1 FROM role_permissions "
                "WHERE role_permissions.role_id = roles.id "
                "AND role_permissions.permission_id = permissions.id)"
            ).bindparams(code=code)
        )


def downgrade() -> None:
    for code, _ in PERMISSIONS:
        op.execute(
            sa.text(
                "DELETE FROM role_permissions "
                "WHERE permission_id IN (SELECT id FROM permissions WHERE code = :code)"
            ).bindparams(code=code)
        )
        op.execute(sa.text("DELETE FROM permissions WHERE code = :code").bindparams(code=code))
