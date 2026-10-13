"""Create the document_sequences table for central document numbering.

Revision ID: 20261013_document_sequences
Revises: 20261013_company_settings
Create Date: 2026-10-13
"""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

from alembic import op

revision = "20261013_document_sequences"
down_revision = "20261013_company_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_sequences",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("doc_type", sa.String(length=50), nullable=False),
        sa.Column("prefix", sa.String(length=30), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("last_number", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("padding", sa.Integer(), server_default=sa.text("4"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doc_type", "year", name="uq_document_sequences_type_year"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_document_sequences_doc_type", "document_sequences", ["doc_type"], unique=False
    )
    op.create_index(
        "ix_document_sequences_year", "document_sequences", ["year"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_document_sequences_year", table_name="document_sequences")
    op.drop_index("ix_document_sequences_doc_type", table_name="document_sequences")
    op.drop_table("document_sequences")