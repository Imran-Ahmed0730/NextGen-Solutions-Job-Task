"""Add auth role state and immutable audit log.

Revision ID: 20261013_auth_audit
Revises: 20261013_auth_models
Create Date: 2026-10-13
"""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

from alembic import op

revision = "20261013_auth_audit"
down_revision = "20261013_auth_models"
branch_labels = None
depends_on = None

id_type = BIGINT(unsigned=True)


def upgrade() -> None:
    op.add_column(
        "roles",
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", id_type, autoincrement=True, nullable=False),
        sa.Column("user_id", id_type, nullable=True),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("before_json", sa.JSON(), nullable=True),
        sa.Column("after_json", sa.JSON(), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index(
        "ix_audit_logs_entity_type_entity_id",
        "audit_logs",
        ["entity_type", "entity_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_entity_type_entity_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_column("roles", "is_active")
