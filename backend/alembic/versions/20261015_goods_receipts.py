"""Add posted goods receipts linked to approved purchase orders."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

from alembic import op

revision = "20261015_goods_receipts"
down_revision = "20261015_po_permissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "goods_receipts",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("doc_no", sa.String(length=50), nullable=False),
        sa.Column("doc_date", sa.Date(), nullable=False),
        sa.Column("po_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("supplier_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("warehouse_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="POSTED", nullable=False),
        sa.Column("total", sa.Numeric(18, 2), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", BIGINT(unsigned=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("status = 'POSTED'", name="ck_goods_receipts_posted_status"),
        sa.CheckConstraint("total >= 0", name="ck_goods_receipts_nonnegative_total"),
        sa.ForeignKeyConstraint(
            ["po_id"],
            ["purchase_orders.id"],
            name="fk_goods_receipts_po_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name="fk_goods_receipts_supplier_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name="fk_goods_receipts_warehouse_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_goods_receipts_created_by",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doc_no", name="uq_goods_receipts_doc_no"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_goods_receipts_supplier_id", "goods_receipts", ["supplier_id"])
    op.create_table(
        "goods_receipt_lines",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("receipt_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("po_line_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("product_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=False),
        sa.Column("line_total", sa.Numeric(18, 2), nullable=False),
        sa.CheckConstraint("qty > 0", name="ck_goods_receipt_lines_positive_qty"),
        sa.CheckConstraint("unit_cost >= 0", name="ck_goods_receipt_lines_nonnegative_unit_cost"),
        sa.CheckConstraint("line_total >= 0", name="ck_goods_receipt_lines_nonnegative_total"),
        sa.ForeignKeyConstraint(
            ["receipt_id"],
            ["goods_receipts.id"],
            name="fk_goods_receipt_lines_receipt_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["po_line_id"],
            ["purchase_order_lines.id"],
            name="fk_goods_receipt_lines_po_line_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_goods_receipt_lines_product_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("receipt_id", "po_line_id", name="uq_goods_receipt_lines_po_line"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_goods_receipt_lines_receipt_id", "goods_receipt_lines", ["receipt_id"])
    op.create_index("ix_goods_receipt_lines_po_line_id", "goods_receipt_lines", ["po_line_id"])
    op.create_index("ix_goods_receipt_lines_product_id", "goods_receipt_lines", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_goods_receipt_lines_product_id", table_name="goods_receipt_lines")
    op.drop_index("ix_goods_receipt_lines_po_line_id", table_name="goods_receipt_lines")
    op.drop_index("ix_goods_receipt_lines_receipt_id", table_name="goods_receipt_lines")
    op.drop_table("goods_receipt_lines")
    op.drop_index("ix_goods_receipts_supplier_id", table_name="goods_receipts")
    op.drop_table("goods_receipts")
