"""Add configurable approval rules."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

from alembic import op

revision = "20261107_approval_rules"
down_revision = "20261106_payroll"
branch_labels = None
depends_on = None

ID = BIGINT(unsigned=True)
PERMISSIONS = (
    ("approvals.rules.read", "View approval rules"),
    ("approvals.rules.create", "Create approval rules"),
    ("approvals.rules.update", "Update and activate approval rules"),
)


def upgrade() -> None:
    op.create_table(
        "approval_rules",
        sa.Column("id", ID, autoincrement=True, nullable=False),
        sa.Column("doc_type", sa.String(length=50), nullable=False),
        sa.Column("min_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("max_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("approver_role_id", ID, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("min_amount >= 0", name="ck_approval_rules_min_nonnegative"),
        sa.CheckConstraint(
            "max_amount IS NULL OR max_amount >= min_amount",
            name="ck_approval_rules_max_gte_min",
        ),
        sa.ForeignKeyConstraint(
            ["approver_role_id"], ["roles.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_approval_rules_document_type", "approval_rules", ["doc_type"]
    )
    op.create_index(
        "ix_approval_rules_approver_role_id", "approval_rules", ["approver_role_id"]
    )

    for code, description in PERMISSIONS:
        op.execute(
            sa.text(
                "INSERT INTO permissions (code, module, description) "
                "SELECT :code, 'approvals', :description "
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
    op.drop_index("ix_approval_rules_approver_role_id", table_name="approval_rules")
    op.drop_index("ix_approval_rules_document_type", table_name="approval_rules")
    op.drop_table("approval_rules")
