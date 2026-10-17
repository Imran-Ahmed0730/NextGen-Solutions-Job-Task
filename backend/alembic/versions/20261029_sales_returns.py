"""Add posted sales returns linked to invoices."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

from alembic import op

revision = "20261029_sales_returns"
down_revision = "20261028_invoices"
branch_labels = None
depends_on = None

PERMISSIONS = (
    ("sales.returns.read", "View sales returns"),
    ("sales.returns.create", "Post sales returns"),
)


def upgrade() -> None:
    op.create_table(
        "sales_returns",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("doc_no", sa.String(length=50), nullable=False),
        sa.Column("doc_date", sa.Date(), nullable=False),
        sa.Column("invoice_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("customer_id", BIGINT(unsigned=True), nullable=False),
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
        sa.CheckConstraint("status = 'POSTED'", name="ck_sales_returns_posted_status"),
        sa.CheckConstraint("total >= 0", name="ck_sales_returns_nonnegative_total"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doc_no", name="uq_sales_returns_doc_no"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_sales_returns_invoice_id", "sales_returns", ["invoice_id"])
    op.create_index("ix_sales_returns_customer_id", "sales_returns", ["customer_id"])
    op.create_table(
        "sales_return_lines",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("return_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("invoice_line_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("product_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(18, 2), nullable=False),
        sa.Column("unit_cost_cogs", sa.Numeric(18, 4), nullable=False),
        sa.CheckConstraint("qty > 0", name="ck_sales_return_lines_positive_qty"),
        sa.CheckConstraint("unit_price >= 0", name="ck_sales_return_lines_nonnegative_unit_price"),
        sa.CheckConstraint("line_total >= 0", name="ck_sales_return_lines_nonnegative_total"),
        sa.CheckConstraint("unit_cost_cogs >= 0", name="ck_sales_return_lines_nonnegative_cogs"),
        sa.ForeignKeyConstraint(["return_id"], ["sales_returns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invoice_line_id"], ["invoice_lines.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("return_id", "invoice_line_id", name="uq_sales_return_lines_source"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_sales_return_lines_return_id", "sales_return_lines", ["return_id"])
    op.create_index(
        "ix_sales_return_lines_invoice_line_id",
        "sales_return_lines",
        ["invoice_line_id"],
    )

    for code, description in PERMISSIONS:
        op.execute(
            sa.text(
                "INSERT INTO permissions (code, module, description) "
                "SELECT :code, 'sales', :description "
                "WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = :code)"
            ).bindparams(code=code, description=description)
        )
        op.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id, permission_id) "
                "SELECT roles.id, permissions.id FROM roles "
                "JOIN permissions ON permissions.code = :code "
                "WHERE roles.name = 'Administrator' "
                "AND NOT EXISTS (SELECT 1 FROM role_permissions "
                "WHERE role_permissions.role_id = roles.id "
                "AND role_permissions.permission_id = permissions.id)"
            ).bindparams(code=code)
        )


def downgrade() -> None:
    for code, _ in PERMISSIONS:
        op.execute(
            sa.text(
                "DELETE FROM role_permissions "
                "WHERE permission_id IN (SELECT id FROM permissions WHERE code = :code)"
            ).bindparams(code=code)
        )
        op.execute(sa.text("DELETE FROM permissions WHERE code = :code").bindparams(code=code))
    op.drop_index("ix_sales_return_lines_invoice_line_id", table_name="sales_return_lines")
    op.drop_index("ix_sales_return_lines_return_id", table_name="sales_return_lines")
    op.drop_table("sales_return_lines")
    op.drop_index("ix_sales_returns_customer_id", table_name="sales_returns")
    op.drop_index("ix_sales_returns_invoice_id", table_name="sales_returns")
    op.drop_table("sales_returns")
