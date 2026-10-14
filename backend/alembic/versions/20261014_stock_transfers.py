"""Add atomic stock transfers.

Revision ID: 20261014_stock_transfers
Revises: 20261014_inventory_ledger
Create Date: 2026-10-14
"""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

from alembic import op

revision = "20261014_stock_transfers"
down_revision = "20261014_inventory_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stock_transfers",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("doc_no", sa.String(length=50), nullable=False),
        sa.Column("doc_date", sa.Date(), nullable=False),
        sa.Column("from_warehouse_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("to_warehouse_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="POSTED", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "from_warehouse_id <> to_warehouse_id",
            name="ck_stock_transfers_distinct_warehouses",
        ),
        sa.ForeignKeyConstraint(
            ["from_warehouse_id"],
            ["warehouses.id"],
            name="fk_stock_transfers_from_warehouse_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["to_warehouse_id"],
            ["warehouses.id"],
            name="fk_stock_transfers_to_warehouse_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doc_no", name="uq_stock_transfers_doc_no"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_table(
        "stock_transfer_lines",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("transfer_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("product_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
        sa.CheckConstraint("qty > 0", name="ck_stock_transfer_lines_positive_qty"),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_stock_transfer_lines_product_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["transfer_id"],
            ["stock_transfers.id"],
            name="fk_stock_transfer_lines_transfer_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )


def downgrade() -> None:
    op.drop_table("stock_transfer_lines")
    op.drop_table("stock_transfers")
