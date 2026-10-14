"""Add Purchase Order drafts."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

from alembic import op

revision = "20261015_purchase_orders"
down_revision = "20261015_pc_permissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_orders",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("doc_no", sa.String(length=50), nullable=False),
        sa.Column("doc_date", sa.Date(), nullable=False),
        sa.Column("supplier_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("warehouse_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="DRAFT", nullable=False),
        sa.Column("expected_date", sa.Date(), nullable=True),
        sa.Column("subtotal", sa.Numeric(18, 2), server_default="0.00", nullable=False),
        sa.Column("discount", sa.Numeric(18, 2), server_default="0.00", nullable=False),
        sa.Column("total", sa.Numeric(18, 2), server_default="0.00", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'PARTIALLY_RECEIVED', "
            "'RECEIVED', 'CLOSED', 'CANCELLED')",
            name="ck_purchase_orders_status",
        ),
        sa.CheckConstraint("subtotal >= 0", name="ck_purchase_orders_nonnegative_subtotal"),
        sa.CheckConstraint("discount >= 0", name="ck_purchase_orders_nonnegative_discount"),
        sa.CheckConstraint("total >= 0", name="ck_purchase_orders_nonnegative_total"),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name="fk_purchase_orders_supplier_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name="fk_purchase_orders_warehouse_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_purchase_orders_created_by",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doc_no", name="uq_purchase_orders_doc_no"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_table(
        "purchase_order_lines",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("po_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("product_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(18, 2), nullable=False),
        sa.Column("received_qty", sa.Numeric(18, 3), server_default="0.000", nullable=False),
        sa.CheckConstraint("qty > 0", name="ck_purchase_order_lines_positive_qty"),
        sa.CheckConstraint(
            "unit_price >= 0", name="ck_purchase_order_lines_nonnegative_unit_price"
        ),
        sa.CheckConstraint("line_total >= 0", name="ck_purchase_order_lines_nonnegative_total"),
        sa.CheckConstraint(
            "received_qty >= 0", name="ck_purchase_order_lines_nonnegative_received_qty"
        ),
        sa.ForeignKeyConstraint(
            ["po_id"],
            ["purchase_orders.id"],
            name="fk_purchase_order_lines_po_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_purchase_order_lines_product_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_purchase_order_lines_po_id", "purchase_order_lines", ["po_id"])
    op.create_index("ix_purchase_order_lines_product_id", "purchase_order_lines", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_purchase_order_lines_product_id", table_name="purchase_order_lines")
    op.drop_index("ix_purchase_order_lines_po_id", table_name="purchase_order_lines")
    op.drop_table("purchase_order_lines")
    op.drop_table("purchase_orders")
