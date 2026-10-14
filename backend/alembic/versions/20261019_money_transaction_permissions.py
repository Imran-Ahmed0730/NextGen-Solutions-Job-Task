"""Add permission for reading account balances."""

import sqlalchemy as sa

from alembic import op

revision = "20261019_money_txn_permissions"
down_revision = "20261018_money_transactions"
branch_labels = None
depends_on = None

PERMISSION = ("money.transactions.read", "View money account balances")


def upgrade() -> None:
    code, description = PERMISSION
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
    code, _ = PERMISSION
    op.execute(
        sa.text(
            "DELETE FROM role_permissions "
            "WHERE permission_id IN (SELECT id FROM permissions WHERE code = :code)"
        ).bindparams(code=code)
    )
    op.execute(sa.text("DELETE FROM permissions WHERE code = :code").bindparams(code=code))
