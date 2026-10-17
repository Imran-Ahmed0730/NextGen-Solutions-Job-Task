"""Add basic payroll runs and salary payment links."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

from alembic import op

revision = "20261106_payroll"
down_revision = "20261105_attendance"
branch_labels = None
depends_on = None

ID = BIGINT(unsigned=True)
PERMISSIONS = (
    ("employees.payroll.read", "View payroll"),
    ("employees.payroll.create", "Create payroll runs"),
    ("employees.payroll.update", "Update draft payroll deductions"),
    ("employees.payroll.post", "Post payroll salary payments"),
)


def upgrade() -> None:
    op.create_table(
        "payroll_runs",
        sa.Column("id", ID, autoincrement=True, nullable=False),
        sa.Column("doc_no", sa.String(length=50), nullable=True),
        sa.Column("period_month", sa.Integer(), nullable=False),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="DRAFT", nullable=False),
        sa.Column(
            "total_amount", sa.Numeric(18, 2), server_default=sa.text("0.00"), nullable=False
        ),
        sa.Column("paid_on", sa.Date(), nullable=True),
        sa.Column("account_id", ID, nullable=True),
        sa.Column("created_by", ID, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("period_month BETWEEN 1 AND 12", name="ck_payroll_runs_month"),
        sa.CheckConstraint("status IN ('DRAFT', 'POSTED')", name="ck_payroll_runs_status"),
        sa.CheckConstraint("total_amount >= 0", name="ck_payroll_runs_total_nonnegative"),
        sa.ForeignKeyConstraint(["account_id"], ["money_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doc_no", name="uq_payroll_runs_doc_no"),
        sa.UniqueConstraint("period_month", "period_year", name="uq_payroll_runs_period"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_table(
        "payroll_lines",
        sa.Column("id", ID, autoincrement=True, nullable=False),
        sa.Column("run_id", ID, nullable=False),
        sa.Column("employee_id", ID, nullable=False),
        sa.Column("base_salary", sa.Numeric(18, 2), nullable=False),
        sa.Column("deductions", sa.Numeric(18, 2), server_default=sa.text("0.00"), nullable=False),
        sa.Column("net_pay", sa.Numeric(18, 2), nullable=False),
        sa.Column("paid_txn_id", ID, nullable=True),
        sa.CheckConstraint("base_salary >= 0", name="ck_payroll_lines_salary_nonnegative"),
        sa.CheckConstraint("deductions >= 0", name="ck_payroll_lines_deductions_nonnegative"),
        sa.CheckConstraint(
            "deductions <= base_salary", name="ck_payroll_lines_deductions_within_salary"
        ),
        sa.CheckConstraint("net_pay >= 0", name="ck_payroll_lines_net_nonnegative"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["paid_txn_id"], ["money_transactions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["run_id"], ["payroll_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "employee_id", name="uq_payroll_lines_run_employee"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_payroll_lines_run_id", "payroll_lines", ["run_id"])
    op.create_index("ix_payroll_lines_employee_id", "payroll_lines", ["employee_id"])

    for code, description in PERMISSIONS:
        op.execute(
            sa.text(
                "INSERT INTO permissions (code, module, description) "
                "SELECT :code, 'employees', :description "
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
    op.drop_index("ix_payroll_lines_employee_id", table_name="payroll_lines")
    op.drop_index("ix_payroll_lines_run_id", table_name="payroll_lines")
    op.drop_table("payroll_lines")
    op.drop_table("payroll_runs")
