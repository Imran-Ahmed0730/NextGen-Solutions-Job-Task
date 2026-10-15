"""Add expenses, incomes, and fund_transfers tables and permissions."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

from alembic import op

revision = "20261022_expenses_incomes_transfers"
down_revision = "20261021_po_status_perms"
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
    op.create_table(
        "expenses",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("doc_no", sa.String(length=50), nullable=False),
        sa.Column("doc_date", sa.Date(), nullable=False),
        sa.Column("category_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("account_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("paid_to", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="POSTED", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", BIGINT(unsigned=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("amount > 0", name="ck_expenses_positive_amount"),
        sa.CheckConstraint("status = 'POSTED'", name="ck_expenses_posted_status"),
        sa.ForeignKeyConstraint(["category_id"], ["expense_categories.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["account_id"], ["money_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doc_no", name="uq_expenses_doc_no"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_expenses_category_id", "expenses", ["category_id"])
    op.create_index("ix_expenses_account_id", "expenses", ["account_id"])

    op.create_table(
        "incomes",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("doc_no", sa.String(length=50), nullable=False),
        sa.Column("doc_date", sa.Date(), nullable=False),
        sa.Column("category_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("account_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="POSTED", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", BIGINT(unsigned=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("amount > 0", name="ck_incomes_positive_amount"),
        sa.CheckConstraint("status = 'POSTED'", name="ck_incomes_posted_status"),
        sa.ForeignKeyConstraint(["category_id"], ["income_categories.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["account_id"], ["money_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doc_no", name="uq_incomes_doc_no"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_incomes_category_id", "incomes", ["category_id"])
    op.create_index("ix_incomes_account_id", "incomes", ["account_id"])

    op.create_table(
        "fund_transfers",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("doc_no", sa.String(length=50), nullable=False),
        sa.Column("doc_date", sa.Date(), nullable=False),
        sa.Column("from_account_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("to_account_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="POSTED", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", BIGINT(unsigned=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("amount > 0", name="ck_fund_transfers_positive_amount"),
        sa.CheckConstraint("status = 'POSTED'", name="ck_fund_transfers_posted_status"),
        sa.CheckConstraint(
            "from_account_id <> to_account_id", name="ck_fund_transfers_different_accounts"
        ),
        sa.ForeignKeyConstraint(["from_account_id"], ["money_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["to_account_id"], ["money_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doc_no", name="uq_fund_transfers_doc_no"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_fund_transfers_from_account", "fund_transfers", ["from_account_id"])
    op.create_index("ix_fund_transfers_to_account", "fund_transfers", ["to_account_id"])

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

    op.drop_index("ix_fund_transfers_to_account", table_name="fund_transfers")
    op.drop_index("ix_fund_transfers_from_account", table_name="fund_transfers")
    op.drop_table("fund_transfers")
    op.drop_index("ix_incomes_account_id", table_name="incomes")
    op.drop_index("ix_incomes_category_id", table_name="incomes")
    op.drop_table("incomes")
    op.drop_index("ix_expenses_account_id", table_name="expenses")
    op.drop_index("ix_expenses_category_id", table_name="expenses")
    op.drop_table("expenses")

