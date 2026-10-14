"""Add minimal sales-order-line persistence and stock reservations.

Revision ID: 20261014_sales_reserve
Revises: 20261014_stock_adjustments
Create Date: 2026-10-14
"""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

from alembic import op

revision = "20261014_sales_reserve"
down_revision = "20261014_stock_adjustments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sales_orders",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("doc_no", sa.String(length=50), nullable=False),
        sa.Column("doc_date", sa.Date(), nullable=False),
        sa.Column("customer_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("warehouse_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="DRAFT", nullable=False),
        sa.Column("delivery_date", sa.Date(), nullable=True),
        sa.Column("subtotal", sa.Numeric(18, 2), server_default=sa.text("0.00"), nullable=False),
        sa.Column("discount", sa.Numeric(18, 2), server_default=sa.text("0.00"), nullable=False),
        sa.Column("total", sa.Numeric(18, 2), server_default=sa.text("0.00"), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.CheckConstraint("subtotal >= 0", name="ck_sales_orders_nonnegative_subtotal"),
        sa.CheckConstraint("discount >= 0", name="ck_sales_orders_nonnegative_discount"),
        sa.CheckConstraint("total >= 0", name="ck_sales_orders_nonnegative_total"),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name="fk_sales_orders_customer_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name="fk_sales_orders_warehouse_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doc_no", name="uq_sales_orders_doc_no"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_table(
        "sales_order_lines",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("order_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("product_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("qty_ordered", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(18, 2), nullable=False),
        sa.Column(
            "qty_reserved", sa.Numeric(18, 3), server_default=sa.text("0.000"), nullable=False
        ),
        sa.Column(
            "qty_produced", sa.Numeric(18, 3), server_default=sa.text("0.000"), nullable=False
        ),
        sa.Column(
            "qty_delivered", sa.Numeric(18, 3), server_default=sa.text("0.000"), nullable=False
        ),
        sa.CheckConstraint("qty_ordered > 0", name="ck_sales_order_lines_positive_ordered_qty"),
        sa.CheckConstraint(
            "qty_reserved >= 0", name="ck_sales_order_lines_nonnegative_reserved_qty"
        ),
        sa.CheckConstraint(
            "qty_produced >= 0", name="ck_sales_order_lines_nonnegative_produced_qty"
        ),
        sa.CheckConstraint(
            "qty_delivered >= 0", name="ck_sales_order_lines_nonnegative_delivered_qty"
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["sales_orders.id"],
            name="fk_sales_order_lines_order_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_sales_order_lines_product_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_sales_order_lines_order_id", "sales_order_lines", ["order_id"])
    op.create_index("ix_sales_order_lines_product_id", "sales_order_lines", ["product_id"])
    op.create_table(
        "stock_reservations",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("sales_order_line_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("product_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("warehouse_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
        sa.Column(
            "qty_consumed", sa.Numeric(18, 3), server_default=sa.text("0.000"), nullable=False
        ),
        sa.Column(
            "qty_released", sa.Numeric(18, 3), server_default=sa.text("0.000"), nullable=False
        ),
        sa.Column("status", sa.String(length=20), server_default="ACTIVE", nullable=False),
        sa.Column("created_by", BIGINT(unsigned=True), nullable=True),
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
        sa.CheckConstraint("qty > 0", name="ck_stock_reservations_positive_qty"),
        sa.CheckConstraint(
            "qty_consumed >= 0 AND qty_released >= 0 AND qty_consumed + qty_released <= qty",
            name="ck_stock_reservations_quantities_within_total",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'RELEASED', 'CONSUMED')",
            name="ck_stock_reservations_status",
        ),
        sa.ForeignKeyConstraint(
            ["sales_order_line_id"],
            ["sales_order_lines.id"],
            name="fk_stock_reservations_sales_order_line_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_stock_reservations_product_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name="fk_stock_reservations_warehouse_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_stock_reservations_created_by",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_stock_reservations_sales_order_line_id",
        "stock_reservations",
        ["sales_order_line_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_stock_reservations_sales_order_line_id", table_name="stock_reservations")
    op.drop_table("stock_reservations")
    op.drop_index("ix_sales_order_lines_product_id", table_name="sales_order_lines")
    op.drop_index("ix_sales_order_lines_order_id", table_name="sales_order_lines")
    op.drop_table("sales_order_lines")
    op.drop_table("sales_orders")
