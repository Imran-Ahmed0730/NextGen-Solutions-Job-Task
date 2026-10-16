"""Add asset register, assignment history, and maintenance log."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

from alembic import op

revision = "20261103_assets"
down_revision = "20261102_production_sales_link"
branch_labels = None
depends_on = None

ID = BIGINT(unsigned=True)
PERMISSIONS = (
    ("assets.read", "View assets"),
    ("assets.create", "Create assets"),
    ("assets.update", "Update and restore assets"),
    ("assets.delete", "Delete assets"),
    ("assets.assign", "Assign assets to locations"),
    ("assets.maintain", "Record asset maintenance"),
)


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", ID, autoincrement=True, nullable=False),
        sa.Column("asset_code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("purchase_date", sa.Date(), nullable=False),
        sa.Column("purchase_cost", sa.Numeric(18, 2), nullable=False),
        sa.Column("location", sa.String(length=150), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="IN_STORE", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", ID, nullable=True),
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
            "status IN ('IN_USE', 'IN_STORE', 'UNDER_MAINTENANCE', 'DISPOSED')",
            name="ck_assets_status",
        ),
        sa.CheckConstraint("purchase_cost >= 0", name="ck_assets_purchase_cost_nonnegative"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_code", name="uq_assets_asset_code"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_table(
        "asset_assignments",
        sa.Column("id", ID, autoincrement=True, nullable=False),
        sa.Column("asset_id", ID, nullable=False),
        sa.Column("location", sa.String(length=150), nullable=False),
        sa.Column("assigned_on", sa.Date(), nullable=False),
        sa.Column("returned_on", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "returned_on IS NULL OR returned_on >= assigned_on",
            name="ck_asset_assignments_return_date",
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_asset_assignments_asset_id", "asset_assignments", ["asset_id"])
    op.create_table(
        "asset_maintenance",
        sa.Column("id", ID, autoincrement=True, nullable=False),
        sa.Column("asset_id", ID, nullable=False),
        sa.Column("maintenance_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("cost", sa.Numeric(18, 2), nullable=False),
        sa.Column("next_due_date", sa.Date(), nullable=True),
        sa.Column("created_by", ID, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("cost >= 0", name="ck_asset_maintenance_cost_nonnegative"),
        sa.CheckConstraint(
            "next_due_date IS NULL OR next_due_date >= maintenance_date",
            name="ck_asset_maintenance_next_due_date",
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_asset_maintenance_asset_id", "asset_maintenance", ["asset_id"])

    for code, description in PERMISSIONS:
        op.execute(
            sa.text(
                "INSERT INTO permissions (code, module, description) "
                "SELECT :code, 'assets', :description "
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
    op.drop_index("ix_asset_maintenance_asset_id", table_name="asset_maintenance")
    op.drop_table("asset_maintenance")
    op.drop_index("ix_asset_assignments_asset_id", table_name="asset_assignments")
    op.drop_table("asset_assignments")
    op.drop_table("assets")
