"""Add stock adjustments.

Revision ID: 20261014_stock_adjustments
Revises: 20261014_stock_transfers
Create Date: 2026-10-14
"""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

from alembic import op

revision = "20261014_stock_adjustments"
down_revision = "20261014_stock_transfers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stock_adjustments",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("doc_no", sa.String(length=50), nullable=False),
        sa.Column("doc_date", sa.Date(), nullable=False),
        sa.Column("warehouse_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="POSTED", nullable=False),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name="fk_stock_adjustments_warehouse_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doc_no", name="uq_stock_adjustments_doc_no"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_table(
        "stock_adjustment_lines",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("adjustment_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("product_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("qty_signed", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=False),
        sa.CheckConstraint("qty_signed <> 0", name="ck_stock_adjustment_lines_nonzero_qty"),
        sa.CheckConstraint("unit_cost >= 0", name="ck_stock_adjustment_lines_nonnegative_cost"),
        sa.ForeignKeyConstraint(
            ["adjustment_id"],
            ["stock_adjustments.id"],
            name="fk_stock_adjustment_lines_adjustment_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_stock_adjustment_lines_product_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )


def downgrade() -> None:
    op.drop_table("stock_adjustment_lines")
    op.drop_table("stock_adjustments")
