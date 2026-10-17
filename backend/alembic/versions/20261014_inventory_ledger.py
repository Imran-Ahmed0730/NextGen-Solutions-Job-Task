"""Add the inventory transaction ledger and stock balances.

Revision ID: 20261014_inventory_ledger
Revises: 20261014_doc_seq_timestamps
Create Date: 2026-10-14
"""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

from alembic import op

revision = "20261014_inventory_ledger"
down_revision = "20261014_doc_seq_timestamps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stock_transactions",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column(
            "txn_date",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("product_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("warehouse_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("movement_type", sa.String(length=30), nullable=False),
        sa.Column("qty_signed", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=True),
        sa.Column("source_id", BIGINT(unsigned=True), nullable=True),
        sa.Column("source_line_id", BIGINT(unsigned=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", BIGINT(unsigned=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("qty_signed <> 0", name="ck_stock_transactions_nonzero_qty"),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_stock_transactions_created_by",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_stock_transactions_product_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name="fk_stock_transactions_warehouse_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_stock_transactions_product_warehouse_date",
        "stock_transactions",
        ["product_id", "warehouse_id", "txn_date"],
        unique=False,
    )
    op.create_index(
        "ix_stock_transactions_source",
        "stock_transactions",
        ["source_type", "source_id"],
        unique=False,
    )

    op.create_table(
        "stock_balances",
        sa.Column("product_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("warehouse_id", BIGINT(unsigned=True), nullable=False),
        sa.Column(
            "qty_on_hand", sa.Numeric(18, 3), server_default=sa.text("0.000"), nullable=False
        ),
        sa.Column(
            "qty_reserved", sa.Numeric(18, 3), server_default=sa.text("0.000"), nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("qty_reserved >= 0", name="ck_stock_balances_reserved_nonnegative"),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_stock_balances_product_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name="fk_stock_balances_warehouse_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("product_id", "warehouse_id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_stock_balances_warehouse_product",
        "stock_balances",
        ["warehouse_id", "product_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_stock_balances_warehouse_product", table_name="stock_balances")
    op.drop_table("stock_balances")
    op.drop_index("ix_stock_transactions_source", table_name="stock_transactions")
    op.drop_index("ix_stock_transactions_product_warehouse_date", table_name="stock_transactions")
    op.drop_table("stock_transactions")
