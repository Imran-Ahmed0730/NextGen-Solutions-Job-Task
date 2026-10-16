"""Add approval requests and decision history."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

from alembic import op

revision = "20261109_approval_workflow"
down_revision = "20261108_employee_links"
branch_labels = None
depends_on = None

ID = BIGINT(unsigned=True)
PERMISSIONS = (
    ("approvals.requests.read", "View pending approvals"),
    ("approvals.requests.decide", "Approve or reject pending requests"),
    ("money.expenses.update", "Edit rejected expenses"),
    ("inventory.adjustments.update", "Edit rejected stock adjustments"),
)


def upgrade() -> None:
    op.drop_constraint("ck_expenses_posted_status", "expenses", type_="check")
    op.create_check_constraint(
        "ck_expenses_status",
        "expenses",
        "status IN ('DRAFT', 'PENDING_APPROVAL', 'POSTED')",
    )
    op.create_check_constraint(
        "ck_stock_adjustments_status",
        "stock_adjustments",
        "status IN ('DRAFT', 'PENDING_APPROVAL', 'POSTED')",
    )

    op.create_table(
        "approval_requests",
        sa.Column("id", ID, autoincrement=True, nullable=False),
        sa.Column("doc_type", sa.String(length=50), nullable=False),
        sa.Column("doc_id", ID, nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("requested_by", ID, nullable=False),
        sa.Column("rule_id", ID, nullable=False),
        sa.Column("status", sa.String(length=20), server_default="PENDING", nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED')",
            name="ck_approval_requests_status",
        ),
        sa.CheckConstraint("amount >= 0", name="ck_approval_requests_amount_nonnegative"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["rule_id"], ["approval_rules.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_approval_requests_document", "approval_requests", ["doc_type", "doc_id"])
    op.create_index(
        "ix_approval_requests_status_requested",
        "approval_requests",
        ["status", "requested_at"],
    )
    op.create_index("ix_approval_requests_requested_by", "approval_requests", ["requested_by"])
    op.create_index("ix_approval_requests_rule_id", "approval_requests", ["rule_id"])

    op.create_table(
        "approval_actions",
        sa.Column("id", ID, autoincrement=True, nullable=False),
        sa.Column("request_id", ID, nullable=False),
        sa.Column("user_id", ID, nullable=False),
        sa.Column("action", sa.String(length=10), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "acted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "action IN ('APPROVE', 'REJECT')",
            name="ck_approval_actions_action",
        ),
        sa.ForeignKeyConstraint(["request_id"], ["approval_requests.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_approval_actions_request", "approval_actions", ["request_id", "acted_at"])
    op.create_index("ix_approval_actions_user_id", "approval_actions", ["user_id"])

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

    op.drop_index("ix_approval_actions_user_id", table_name="approval_actions")
    op.drop_index("ix_approval_actions_request", table_name="approval_actions")
    op.drop_table("approval_actions")
    op.drop_index("ix_approval_requests_rule_id", table_name="approval_requests")
    op.drop_index("ix_approval_requests_requested_by", table_name="approval_requests")
    op.drop_index("ix_approval_requests_status_requested", table_name="approval_requests")
    op.drop_index("ix_approval_requests_document", table_name="approval_requests")
    op.drop_table("approval_requests")
    op.drop_constraint("ck_stock_adjustments_status", "stock_adjustments", type_="check")
    op.drop_constraint("ck_expenses_status", "expenses", type_="check")
    op.create_check_constraint("ck_expenses_posted_status", "expenses", "status = 'POSTED'")
