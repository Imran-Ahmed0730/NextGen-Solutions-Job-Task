"""Create customer, supplier, and party contact tables.

Revision ID: 20261014_customers_suppliers
Revises: 20261013_document_sequences
Create Date: 2026-10-14
"""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

from alembic import op

revision = "20261014_customers_suppliers"
down_revision = "20261013_document_sequences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("mobile", sa.String(length=30), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column(
            "credit_limit", sa.Numeric(18, 2), server_default=sa.text("0.00"), nullable=False
        ),
        sa.Column(
            "opening_due", sa.Numeric(18, 2), server_default=sa.text("0.00"), nullable=False
        ),
        sa.Column("price_list_id", BIGINT(unsigned=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["price_list_id"],
            ["price_lists.id"],
            name="fk_customers_price_list_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_customers_code"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_customers_code", "customers", ["code"], unique=False)
    op.create_index("ix_customers_price_list_id", "customers", ["price_list_id"], unique=False)

    op.create_table(
        "suppliers",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("mobile", sa.String(length=30), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("opening_due", sa.Numeric(18, 2), server_default=sa.text("0.00"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_suppliers_code"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_suppliers_code", "suppliers", ["code"], unique=False)

    op.create_table(
        "party_contacts",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("party_type", sa.String(length=20), nullable=False),
        sa.Column("party_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("designation", sa.String(length=100), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_party_contacts_party", "party_contacts", ["party_type", "party_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_party_contacts_party", table_name="party_contacts")
    op.drop_table("party_contacts")
    op.drop_index("ix_suppliers_code", table_name="suppliers")
    op.drop_table("suppliers")
    op.drop_index("ix_customers_price_list_id", table_name="customers")
    op.drop_index("ix_customers_code", table_name="customers")
    op.drop_table("customers")