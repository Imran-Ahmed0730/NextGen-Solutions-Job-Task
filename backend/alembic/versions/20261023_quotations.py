"""Add quotation drafts and sales quotation permissions."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

from alembic import op

revision = "20261023_quotations"
down_revision = "20261022_expenses_incomes_transfers"
branch_labels = None
depends_on = None

PERMISSIONS = (
    ("sales.quotations.read", "View quotations"),
    ("sales.quotations.create", "Create quotations"),
    ("sales.quotations.update", "Update draft quotations"),
)


def upgrade() -> None:
    op.create_table(
        "quotations",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("doc_no", sa.String(length=50), nullable=False),
        sa.Column("doc_date", sa.Date(), nullable=False),
        sa.Column("customer_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="DRAFT", nullable=False),
        sa.Column("subtotal", sa.Numeric(18, 2), server_default=sa.text("0.00"), nullable=False),
        sa.Column("discount", sa.Numeric(18, 2), server_default=sa.text("0.00"), nullable=False),
        sa.Column("total", sa.Numeric(18, 2), server_default=sa.text("0.00"), nullable=False),
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
        sa.CheckConstraint("subtotal >= 0", name="ck_quotations_nonnegative_subtotal"),
        sa.CheckConstraint("discount >= 0", name="ck_quotations_nonnegative_discount"),
        sa.CheckConstraint("total >= 0", name="ck_quotations_nonnegative_total"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doc_no", name="uq_quotations_doc_no"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_quotations_customer_id", "quotations", ["customer_id"])
    op.create_table(
        "quotation_lines",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("quotation_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("product_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(18, 2), nullable=False),
        sa.CheckConstraint("qty > 0", name="ck_quotation_lines_positive_qty"),
        sa.CheckConstraint("unit_price >= 0", name="ck_quotation_lines_nonnegative_unit_price"),
        sa.CheckConstraint("line_total >= 0", name="ck_quotation_lines_nonnegative_total"),
        sa.ForeignKeyConstraint(["quotation_id"], ["quotations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quotation_lines_quotation_id", "quotation_lines", ["quotation_id"])
    op.create_index("ix_quotation_lines_product_id", "quotation_lines", ["product_id"])

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

    op.drop_index("ix_quotation_lines_product_id", table_name="quotation_lines")
    op.drop_index("ix_quotation_lines_quotation_id", table_name="quotation_lines")
    op.drop_table("quotation_lines")
    op.drop_index("ix_quotations_customer_id", table_name="quotations")
    op.drop_table("quotations")
