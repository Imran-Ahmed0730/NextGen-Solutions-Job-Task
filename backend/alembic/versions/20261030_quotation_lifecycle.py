"""Add quotation status lifecycle and one-time sales order conversion."""

from alembic import op

revision = "20261030_quotation_lifecycle"
down_revision = "20261029_sales_returns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_quotations_valid_status",
        "quotations",
        "status IN ('DRAFT', 'SENT', 'ACCEPTED', 'REJECTED')",
    )
    op.create_unique_constraint(
        "uq_sales_orders_quotation_id",
        "sales_orders",
        ["quotation_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_sales_orders_quotation_id", "sales_orders", type_="unique")
    op.drop_constraint("ck_quotations_valid_status", "quotations", type_="check")
