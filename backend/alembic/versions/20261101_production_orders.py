"""Add production orders and posting snapshots."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

from alembic import op

revision = "20261101_production_orders"
down_revision = "20261031_boms"
branch_labels = None
depends_on = None

PERMISSIONS = (
    ("production.orders.read", "View production orders"),
    ("production.orders.create", "Create production orders"),
    ("production.orders.update", "Update and post production orders"),
)


def upgrade() -> None:
    op.create_table(
        "production_orders",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("doc_no", sa.String(length=50), nullable=False),
        sa.Column("doc_date", sa.Date(), nullable=False),
        sa.Column("bom_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("finished_product_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("planned_qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("actual_qty", sa.Numeric(18, 3), nullable=True),
        sa.Column("warehouse_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="DRAFT", nullable=False),
        sa.Column("labor_cost", sa.Numeric(18, 2), nullable=True),
        sa.Column("overhead_cost", sa.Numeric(18, 2), nullable=True),
        sa.Column("material_cost", sa.Numeric(18, 2), nullable=True),
        sa.Column("total_cost", sa.Numeric(18, 2), nullable=True),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=True),
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
            "status IN ('DRAFT', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')",
            name="ck_production_orders_status",
        ),
        sa.CheckConstraint("planned_qty > 0", name="ck_production_orders_positive_planned_qty"),
        sa.CheckConstraint(
            "actual_qty IS NULL OR actual_qty > 0",
            name="ck_production_orders_positive_actual_qty",
        ),
        sa.ForeignKeyConstraint(["bom_id"], ["boms.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["finished_product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doc_no", name="uq_production_orders_doc_no"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_production_orders_bom_id", "production_orders", ["bom_id"])
    op.create_table(
        "production_consumption",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("production_order_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("product_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=False),
        sa.Column("line_cost", sa.Numeric(18, 2), nullable=False),
        sa.CheckConstraint("qty > 0", name="ck_production_consumption_positive_qty"),
        sa.CheckConstraint(
            "unit_cost >= 0", name="ck_production_consumption_nonnegative_unit_cost"
        ),
        sa.CheckConstraint(
            "line_cost >= 0", name="ck_production_consumption_nonnegative_line_cost"
        ),
        sa.ForeignKeyConstraint(
            ["production_order_id"], ["production_orders.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "production_order_id", "product_id", name="uq_production_consumption_product"
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_production_consumption_production_order_id",
        "production_consumption",
        ["production_order_id"],
    )
    op.create_table(
        "production_outputs",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("production_order_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("product_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=False),
        sa.CheckConstraint("qty > 0", name="ck_production_outputs_positive_qty"),
        sa.CheckConstraint("unit_cost >= 0", name="ck_production_outputs_nonnegative_unit_cost"),
        sa.ForeignKeyConstraint(
            ["production_order_id"], ["production_orders.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("production_order_id", name="uq_production_outputs_order"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_production_outputs_production_order_id",
        "production_outputs",
        ["production_order_id"],
    )

    for code, description in PERMISSIONS:
        op.execute(
            sa.text(
                "INSERT INTO permissions (code, module, description) "
                "SELECT :code, 'production', :description "
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
    op.drop_index("ix_production_outputs_production_order_id", table_name="production_outputs")
    op.drop_table("production_outputs")
    op.drop_index(
        "ix_production_consumption_production_order_id", table_name="production_consumption"
    )
    op.drop_table("production_consumption")
    op.drop_index("ix_production_orders_bom_id", table_name="production_orders")
    op.drop_table("production_orders")
