"""Add posted sales invoices linked to deliveries."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

from alembic import op

revision = "20261028_invoices"
down_revision = "20261027_deliveries"
branch_labels = None
depends_on = None

PERMISSIONS = (
    ("sales.invoices.read", "View sales invoices"),
    ("sales.invoices.create", "Post sales invoices"),
)


def upgrade() -> None:
    op.create_table(
        "invoices",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("doc_no", sa.String(length=50), nullable=False),
        sa.Column("doc_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("customer_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("delivery_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="POSTED", nullable=False),
        sa.Column("subtotal", sa.Numeric(18, 2), nullable=False),
        sa.Column("discount", sa.Numeric(18, 2), nullable=False),
        sa.Column("total", sa.Numeric(18, 2), nullable=False),
        sa.Column("cogs_total", sa.Numeric(18, 2), nullable=False),
        sa.Column("created_by", BIGINT(unsigned=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("subtotal >= 0", name="ck_invoices_nonnegative_subtotal"),
        sa.CheckConstraint("discount >= 0", name="ck_invoices_nonnegative_discount"),
        sa.CheckConstraint("total >= 0", name="ck_invoices_nonnegative_total"),
        sa.CheckConstraint("cogs_total >= 0", name="ck_invoices_nonnegative_cogs"),
        sa.CheckConstraint("status = 'POSTED'", name="ck_invoices_posted_status"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["delivery_id"], ["deliveries.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doc_no", name="uq_invoices_doc_no"),
        sa.UniqueConstraint("delivery_id", name="uq_invoices_delivery_id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_invoices_customer_id", "invoices", ["customer_id"])
    op.create_table(
        "invoice_lines",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("invoice_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("product_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(18, 2), nullable=False),
        sa.Column("unit_cost_cogs", sa.Numeric(18, 4), nullable=False),
        sa.CheckConstraint("qty > 0", name="ck_invoice_lines_positive_qty"),
        sa.CheckConstraint("unit_price >= 0", name="ck_invoice_lines_nonnegative_unit_price"),
        sa.CheckConstraint("line_total >= 0", name="ck_invoice_lines_nonnegative_total"),
        sa.CheckConstraint("unit_cost_cogs >= 0", name="ck_invoice_lines_nonnegative_cogs"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_invoice_lines_invoice_id", "invoice_lines", ["invoice_id"])

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
    op.drop_index("ix_invoice_lines_invoice_id", table_name="invoice_lines")
    op.drop_table("invoice_lines")
    op.drop_index("ix_invoices_customer_id", table_name="invoices")
    op.drop_table("invoices")
