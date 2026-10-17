"""Create the master-data money_accounts table.

Revision ID: 20261013_money_accounts
Revises: 20261013_payment_methods
Create Date: 2026-10-13
"""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

from alembic import op

revision = "20261013_money_accounts"
down_revision = "20261013_payment_methods"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "money_accounts",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("payment_method_id", BIGINT(unsigned=True), nullable=True),
        sa.Column("account_no", sa.String(length=50), nullable=True),
        sa.Column(
            "opening_balance",
            sa.Numeric(precision=18, scale=2),
            server_default=sa.text("0.00"),
            nullable=False,
        ),
        sa.Column(
            "allow_overdraft",
            sa.Boolean(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["payment_method_id"],
            ["payment_methods.id"],
            name="fk_money_accounts_payment_method_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_money_accounts_payment_method_id",
        "money_accounts",
        ["payment_method_id"],
        unique=False,
    )
    op.create_index("ix_money_accounts_type", "money_accounts", ["type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_money_accounts_type", table_name="money_accounts")
    op.drop_index("ix_money_accounts_payment_method_id", table_name="money_accounts")
    op.drop_table("money_accounts")
