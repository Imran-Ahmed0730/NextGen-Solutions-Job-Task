"""Create the master-data company_settings key/value table.

Revision ID: 20261013_company_settings
Revises: 20261013_price_lists
Create Date: 2026-10-13
"""

import sqlalchemy as sa

from alembic import op

revision = "20261013_company_settings"
down_revision = "20261013_price_lists"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_settings",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )


def downgrade() -> None:
    op.drop_table("company_settings")
