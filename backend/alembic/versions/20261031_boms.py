"""Add bills of materials."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

from alembic import op

revision = "20261031_boms"
down_revision = "20261030_quotation_lifecycle"
branch_labels = None
depends_on = None

PERMISSIONS = (
    ("production.boms.read", "View bills of materials"),
    ("production.boms.create", "Create bills of materials"),
    ("production.boms.update", "Update bills of materials"),
    ("production.boms.delete", "Delete bills of materials"),
)


def upgrade() -> None:
    op.create_table(
        "boms",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("finished_product_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("output_qty", sa.Numeric(18, 3), nullable=False),
        sa.Column(
            "labor_cost_default",
            sa.Numeric(18, 2),
            server_default=sa.text("0.00"),
            nullable=False,
        ),
        sa.Column(
            "overhead_cost_default",
            sa.Numeric(18, 2),
            server_default=sa.text("0.00"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
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
        sa.CheckConstraint("output_qty > 0", name="ck_boms_positive_output_qty"),
        sa.CheckConstraint("labor_cost_default >= 0", name="ck_boms_nonnegative_labor"),
        sa.CheckConstraint("overhead_cost_default >= 0", name="ck_boms_nonnegative_overhead"),
        sa.ForeignKeyConstraint(
            ["finished_product_id"], ["products.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_boms_code"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_boms_finished_product_id", "boms", ["finished_product_id"])
    op.create_table(
        "bom_lines",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("bom_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("raw_product_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
        sa.CheckConstraint("qty > 0", name="ck_bom_lines_positive_qty"),
        sa.ForeignKeyConstraint(["bom_id"], ["boms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["raw_product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bom_id", "raw_product_id", name="uq_bom_lines_component"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_bom_lines_bom_id", "bom_lines", ["bom_id"])

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
    op.drop_index("ix_bom_lines_bom_id", table_name="bom_lines")
    op.drop_table("bom_lines")
    op.drop_index("ix_boms_finished_product_id", table_name="boms")
    op.drop_table("boms")
