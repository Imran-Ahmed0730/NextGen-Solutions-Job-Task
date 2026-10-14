"""Add purchase returns linked to original goods receipt lines."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

from alembic import op

revision = "20261017_purchase_returns"
down_revision = "20261016_dp_permissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_returns",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("doc_no", sa.String(length=50), nullable=False),
        sa.Column("doc_date", sa.Date(), nullable=False),
        sa.Column("receipt_id", BIGINT(unsigned=True), nullable=False),
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
        sa.CheckConstraint("status = 'POSTED'", name="ck_purchase_returns_posted_status"),
        sa.CheckConstraint("total >= 0", name="ck_purchase_returns_nonnegative_total"),
        sa.ForeignKeyConstraint(
            ["receipt_id"],
            ["goods_receipts.id"],
            name="fk_purchase_returns_receipt_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name="fk_purchase_returns_supplier_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name="fk_purchase_returns_warehouse_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_purchase_returns_created_by",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doc_no", name="uq_purchase_returns_doc_no"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_purchase_returns_supplier_id", "purchase_returns", ["supplier_id"])
    op.create_table(
        "purchase_return_lines",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("return_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("receipt_line_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("product_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=False),
        sa.Column("line_total", sa.Numeric(18, 2), nullable=False),
        sa.CheckConstraint("qty > 0", name="ck_purchase_return_lines_positive_qty"),
        sa.CheckConstraint("unit_cost >= 0", name="ck_purchase_return_lines_nonnegative_unit_cost"),
        sa.CheckConstraint("line_total >= 0", name="ck_purchase_return_lines_nonnegative_total"),
        sa.ForeignKeyConstraint(
            ["return_id"],
            ["purchase_returns.id"],
            name="fk_purchase_return_lines_return_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["receipt_line_id"],
            ["goods_receipt_lines.id"],
            name="fk_purchase_return_lines_receipt_line_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_purchase_return_lines_product_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("return_id", "receipt_line_id", name="uq_purchase_return_lines_source"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_purchase_return_lines_return_id", "purchase_return_lines", ["return_id"])
    op.create_index(
        "ix_purchase_return_lines_receipt_line_id",
        "purchase_return_lines",
        ["receipt_line_id"],
    )
    op.create_index("ix_purchase_return_lines_product_id", "purchase_return_lines", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_purchase_return_lines_product_id", table_name="purchase_return_lines")
    op.drop_index("ix_purchase_return_lines_receipt_line_id", table_name="purchase_return_lines")
    op.drop_index("ix_purchase_return_lines_return_id", table_name="purchase_return_lines")
    op.drop_table("purchase_return_lines")
    op.drop_index("ix_purchase_returns_supplier_id", table_name="purchase_returns")
    op.drop_table("purchase_returns")
