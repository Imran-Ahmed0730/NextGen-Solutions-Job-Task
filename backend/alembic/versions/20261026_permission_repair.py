"""Restore missing money permissions and Administrator assignments."""

import sqlalchemy as sa

from alembic import op

revision = "20261026_perm_repair"
down_revision = "20261025_so_reservations"
branch_labels = None
depends_on = None

PERMISSIONS = (
    ("money.expenses.read", "View expenses"),
    ("money.expenses.create", "Create expenses"),
    ("money.incomes.read", "View incomes"),
    ("money.incomes.create", "Create incomes"),
    ("money.transfers.read", "View fund transfers"),
    ("money.transfers.create", "Create fund transfers"),
)


def upgrade() -> None:
    for code, description in PERMISSIONS:
        op.execute(
            sa.text(
                "INSERT INTO permissions (code, module, description) "
                "SELECT :code, 'money', :description "
                "WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = :code)"
            ).bindparams(code=code, description=description)
        )
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
