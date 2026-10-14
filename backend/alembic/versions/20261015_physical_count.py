"""Add physical count sheets."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

from alembic import op

revision = "20261015_physical_count"
down_revision = "20261014_sales_reserve"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "physical_counts",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("doc_no", sa.String(length=50), nullable=True),
        sa.Column("count_date", sa.Date(), nullable=False),
        sa.Column("warehouse_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="OPEN", nullable=False),
        sa.Column("created_by", BIGINT(unsigned=True), nullable=True),
        sa.Column("posted_by", BIGINT(unsigned=True), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('OPEN', 'COUNTED', 'POSTED')",
            name="ck_physical_counts_status",
        ),
        sa.CheckConstraint(
            "(status = 'POSTED' AND doc_no IS NOT NULL AND posted_at IS NOT NULL) "
            "OR (status IN ('OPEN', 'COUNTED') AND doc_no IS NULL AND posted_at IS NULL)",
            name="ck_physical_counts_posting_fields",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name="fk_physical_counts_warehouse_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_physical_counts_created_by",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["posted_by"],
            ["users.id"],
            name="fk_physical_counts_posted_by",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doc_no", name="uq_physical_counts_doc_no"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_table(
        "physical_count_lines",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("count_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("product_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("system_qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("counted_qty", sa.Numeric(18, 3), nullable=True),
        sa.Column("variance_qty", sa.Numeric(18, 3), nullable=True),
        sa.CheckConstraint(
            "system_qty >= 0",
            name="ck_physical_count_lines_system_qty_nonnegative",
        ),
        sa.CheckConstraint(
            "counted_qty IS NULL OR counted_qty >= 0",
            name="ck_physical_count_lines_counted_qty_nonnegative",
        ),
        sa.CheckConstraint(
            "(counted_qty IS NULL AND variance_qty IS NULL) "
            "OR (counted_qty IS NOT NULL AND variance_qty IS NOT NULL)",
            name="ck_physical_count_lines_count_and_variance",
        ),
        sa.ForeignKeyConstraint(
            ["count_id"],
            ["physical_counts.id"],
            name="fk_physical_count_lines_count_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_physical_count_lines_product_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("count_id", "product_id", name="uq_physical_count_lines_count_product"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )


def downgrade() -> None:
    op.drop_table("physical_count_lines")
    op.drop_table("physical_counts")
