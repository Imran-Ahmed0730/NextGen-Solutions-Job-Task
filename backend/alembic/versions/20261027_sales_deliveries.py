"""Add posted sales delivery documents and permissions."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

from alembic import op

revision = "20261027_deliveries"
down_revision = "20261026_perm_repair"
branch_labels = None
depends_on = None

PERMISSION = ("sales.deliveries.create", "Post sales deliveries")


def upgrade() -> None:
    op.create_table(
        "deliveries",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("doc_no", sa.String(length=50), nullable=False),
        sa.Column("doc_date", sa.Date(), nullable=False),
        sa.Column("order_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("customer_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("warehouse_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="POSTED", nullable=False),
        sa.Column("created_by", BIGINT(unsigned=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("status = 'POSTED'", name="ck_deliveries_posted_status"),
        sa.ForeignKeyConstraint(["order_id"], ["sales_orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doc_no", name="uq_deliveries_doc_no"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_deliveries_order_id", "deliveries", ["order_id"])

    op.create_table(
        "delivery_lines",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("delivery_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("order_line_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("product_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_cost_cogs", sa.Numeric(18, 4), nullable=False),
        sa.CheckConstraint("qty > 0", name="ck_delivery_lines_positive_qty"),
        sa.CheckConstraint("unit_cost_cogs >= 0", name="ck_delivery_lines_nonnegative_cogs"),
        sa.ForeignKeyConstraint(["delivery_id"], ["deliveries.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["order_line_id"], ["sales_order_lines.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_delivery_lines_delivery_id", "delivery_lines", ["delivery_id"])

    code, description = PERMISSION
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
    code, _ = PERMISSION
    op.execute(
        sa.text(
            "DELETE FROM role_permissions "
            "WHERE permission_id IN (SELECT id FROM permissions WHERE code = :code)"
        ).bindparams(code=code)
    )
    op.execute(sa.text("DELETE FROM permissions WHERE code = :code").bindparams(code=code))
    op.drop_index("ix_delivery_lines_delivery_id", table_name="delivery_lines")
    op.drop_table("delivery_lines")
    op.drop_index("ix_deliveries_order_id", table_name="deliveries")
    op.drop_table("deliveries")
