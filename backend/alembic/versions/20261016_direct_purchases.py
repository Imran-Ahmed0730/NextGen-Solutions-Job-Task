"""Add credit-only direct purchase documents and lines."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

from alembic import op

revision = "20261016_direct_purchases"
down_revision = "20261015_gr_permissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "direct_purchases",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("doc_no", sa.String(length=50), nullable=False),
        sa.Column("doc_date", sa.Date(), nullable=False),
        sa.Column("supplier_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("warehouse_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="POSTED", nullable=False),
        sa.Column("total", sa.Numeric(18, 2), nullable=False),
        sa.Column("paid_amount", sa.Numeric(18, 2), server_default=sa.text("0.00"), nullable=False),
        sa.Column("money_account_id", BIGINT(unsigned=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", BIGINT(unsigned=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("status = 'POSTED'", name="ck_direct_purchases_posted_status"),
        sa.CheckConstraint("total >= 0", name="ck_direct_purchases_nonnegative_total"),
        sa.CheckConstraint("paid_amount = 0", name="ck_direct_purchases_credit_only"),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name="fk_direct_purchases_supplier_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name="fk_direct_purchases_warehouse_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["money_account_id"],
            ["money_accounts.id"],
            name="fk_direct_purchases_money_account_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_direct_purchases_created_by",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doc_no", name="uq_direct_purchases_doc_no"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_direct_purchases_supplier_id", "direct_purchases", ["supplier_id"])
    op.create_table(
        "direct_purchase_lines",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("purchase_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("product_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=False),
        sa.Column("line_total", sa.Numeric(18, 2), nullable=False),
        sa.CheckConstraint("qty > 0", name="ck_direct_purchase_lines_positive_qty"),
        sa.CheckConstraint("unit_cost >= 0", name="ck_direct_purchase_lines_nonnegative_unit_cost"),
        sa.CheckConstraint("line_total >= 0", name="ck_direct_purchase_lines_nonnegative_total"),
        sa.ForeignKeyConstraint(
            ["purchase_id"],
            ["direct_purchases.id"],
            name="fk_direct_purchase_lines_purchase_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_direct_purchase_lines_product_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_direct_purchase_lines_purchase_id", "direct_purchase_lines", ["purchase_id"]
    )
    op.create_index("ix_direct_purchase_lines_product_id", "direct_purchase_lines", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_direct_purchase_lines_product_id", table_name="direct_purchase_lines")
    op.drop_index("ix_direct_purchase_lines_purchase_id", table_name="direct_purchase_lines")
    op.drop_table("direct_purchase_lines")
    op.drop_index("ix_direct_purchases_supplier_id", table_name="direct_purchases")
    op.drop_table("direct_purchases")
