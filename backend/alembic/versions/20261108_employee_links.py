"""Link user accounts and asset assignments to employees."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

from alembic import op

revision = "20261108_employee_links"
down_revision = "20261107_approval_rules"
branch_labels = None
depends_on = None

ID = BIGINT(unsigned=True)


def upgrade() -> None:
    op.create_index("ix_users_employee_id", "users", ["employee_id"])
    op.create_foreign_key(
        "fk_users_employee_id_employees",
        "users",
        "employees",
        ["employee_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.add_column(
        "asset_assignments",
        sa.Column("employee_id", ID, nullable=True),
    )
    op.create_index("ix_asset_assignments_employee_id", "asset_assignments", ["employee_id"])
    op.create_foreign_key(
        "fk_asset_assignments_employee_id_employees",
        "asset_assignments",
        "employees",
        ["employee_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_asset_assignments_employee_id_employees",
        "asset_assignments",
        type_="foreignkey",
    )
    op.drop_index("ix_asset_assignments_employee_id", table_name="asset_assignments")
    op.drop_column("asset_assignments", "employee_id")
    op.drop_constraint("fk_users_employee_id_employees", "users", type_="foreignkey")
    op.drop_index("ix_users_employee_id", table_name="users")
