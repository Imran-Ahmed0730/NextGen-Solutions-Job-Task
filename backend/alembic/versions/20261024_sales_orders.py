"""Complete sales order draft documents and add sales order permissions."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

from alembic import op

revision = "20261024_sales_orders"
down_revision = "20261023_quotations"
branch_labels = None
depends_on = None

PERMISSIONS = (
    ("sales.orders.read", "View sales orders"),
    ("sales.orders.create", "Create sales orders"),
    ("sales.orders.update", "Update draft sales orders"),
)


def upgrade() -> None:
    op.add_column(
        "sales_orders",
        sa.Column("quotation_id", BIGINT(unsigned=True), nullable=True),
    )
    op.add_column(
        "sales_orders",
        sa.Column("created_by", BIGINT(unsigned=True), nullable=True),
    )
    op.add_column(
        "sales_orders",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.add_column(
        "sales_orders",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_sales_orders_quotation_id",
        "sales_orders",
        "quotations",
        ["quotation_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_sales_orders_created_by",
        "sales_orders",
        "users",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_sales_orders_quotation_id", "sales_orders", ["quotation_id"])

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

    op.drop_index("ix_sales_orders_quotation_id", table_name="sales_orders")
    op.drop_constraint("fk_sales_orders_created_by", "sales_orders", type_="foreignkey")
    op.drop_constraint("fk_sales_orders_quotation_id", "sales_orders", type_="foreignkey")
    op.drop_column("sales_orders", "updated_at")
    op.drop_column("sales_orders", "created_at")
    op.drop_column("sales_orders", "created_by")
    op.drop_column("sales_orders", "quotation_id")
