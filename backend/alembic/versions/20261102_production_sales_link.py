"""Link production output to sales-order lines."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

from alembic import op

revision = "20261102_production_sales_link"
down_revision = "20261101_production_orders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "production_orders",
        sa.Column("sales_order_line_id", BIGINT(unsigned=True), nullable=True),
    )
    op.create_index(
        "ix_production_orders_sales_order_line_id",
        "production_orders",
        ["sales_order_line_id"],
    )
    op.create_foreign_key(
        "fk_production_orders_sales_order_line_id",
        "production_orders",
        "sales_order_lines",
        ["sales_order_line_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_production_orders_sales_order_line_id",
        "production_orders",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_production_orders_sales_order_line_id",
        table_name="production_orders",
    )
    op.drop_column("production_orders", "sales_order_line_id")
