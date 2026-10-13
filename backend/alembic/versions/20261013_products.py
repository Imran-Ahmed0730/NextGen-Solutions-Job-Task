"""Create products table.

Revision ID: 20261013_products
Revises: 20261013_categories
Create Date: 2026-10-13
"""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

from alembic import op

revision = "20261013_products"
down_revision = "20261013_categories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("sku", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("category_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("unit_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("is_stocked", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "reorder_level",
            sa.Numeric(precision=18, scale=3),
            server_default=sa.text("0.000"),
            nullable=False,
        ),
        sa.Column(
            "avg_cost",
            sa.Numeric(precision=18, scale=4),
            server_default=sa.text("0.0000"),
            nullable=False,
        ),
        sa.Column(
            "sales_price_default",
            sa.Numeric(precision=18, scale=2),
            server_default=sa.text("0.00"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
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
            ["category_id"],
            ["product_categories.id"],
            name="fk_products_category_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["unit_id"],
            ["units.id"],
            name="fk_products_unit_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sku", name="uq_products_sku"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_products_category_id", "products", ["category_id"], unique=False)
    op.create_index("ix_products_unit_id", "products", ["unit_id"], unique=False)
    op.create_index("ix_products_type", "products", ["type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_products_type", table_name="products")
    op.drop_index("ix_products_unit_id", table_name="products")
    op.drop_index("ix_products_category_id", table_name="products")
    op.drop_table("products")
