"""Create the master-data expense_categories table.

Revision ID: 20261013_expense_categories
Revises: 20261013_warehouses
Create Date: 2026-10-13
"""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

from alembic import op

revision = "20261013_expense_categories"
down_revision = "20261013_warehouses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "expense_categories",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("parent_id", BIGINT(unsigned=True), nullable=True),
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
            ["parent_id"],
            ["expense_categories.id"],
            name="fk_expense_categories_parent_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_expense_categories_parent_id",
        "expense_categories",
        ["parent_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_expense_categories_parent_id", table_name="expense_categories")
    op.drop_table("expense_categories")
