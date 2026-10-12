"""Remove obsolete operator-issued password reset permission.

Revision ID: 20261013_remove_operator_reset_permission
Revises: 20261013_auth_audit
Create Date: 2026-10-13
"""

import sqlalchemy as sa

from alembic import op

revision = "20261013_remove_operator_reset_permission"
down_revision = "20261013_auth_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM role_permissions "
            "WHERE permission_id IN "
            "(SELECT id FROM permissions WHERE code = 'auth.users.reset_password')"
        )
    )
    op.execute(
        sa.text("DELETE FROM permissions WHERE code = 'auth.users.reset_password'")
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO permissions (code, module, description) "
            "SELECT 'auth.users.reset_password', 'auth', 'Issue a password reset token' "
            "WHERE NOT EXISTS "
            "(SELECT id FROM permissions WHERE code = 'auth.users.reset_password')"
        )
    )
