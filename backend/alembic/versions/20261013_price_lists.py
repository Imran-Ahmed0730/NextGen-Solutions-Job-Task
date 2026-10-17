"""Create the master-data price_lists and product_prices tables.

Revision ID: 20261013_price_lists
Revises: 20261013_money_accounts
Create Date: 2026-10-13
"""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

from alembic import op

revision = "20261013_price_lists"
down_revision = "20261013_money_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "price_lists",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_price_lists_is_default", "price_lists", ["is_default"], unique=False)
    op.create_index("ix_price_lists_valid_from", "price_lists", ["valid_from"], unique=False)
    op.create_index("ix_price_lists_valid_to", "price_lists", ["valid_to"], unique=False)

    op.create_table(
        "product_prices",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("price_list_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("product_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("price", sa.Numeric(18, 2), nullable=False),
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
            ["price_list_id"],
            ["price_lists.id"],
            name="fk_product_prices_price_list_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_product_prices_product_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("price_list_id", "product_id", name="uq_product_prices_list_product"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_product_prices_price_list_id",
        "product_prices",
        ["price_list_id"],
        unique=False,
    )
    op.create_index("ix_product_prices_product_id", "product_prices", ["product_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_product_prices_product_id", table_name="product_prices")
    op.drop_index("ix_product_prices_price_list_id", table_name="product_prices")
    op.drop_table("product_prices")
    op.drop_index("ix_price_lists_valid_to", table_name="price_lists")
    op.drop_index("ix_price_lists_valid_from", table_name="price_lists")
    op.drop_index("ix_price_lists_is_default", table_name="price_lists")
    op.drop_table("price_lists")
