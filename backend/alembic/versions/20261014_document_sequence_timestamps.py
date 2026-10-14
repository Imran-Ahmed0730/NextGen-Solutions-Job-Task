"""Add timestamps to document sequences.

Revision ID: 20261014_doc_seq_timestamps
Revises: 20261014_customers_suppliers
Create Date: 2026-10-14
"""

import sqlalchemy as sa

from alembic import op

revision = "20261014_doc_seq_timestamps"
down_revision = "20261014_customers_suppliers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_sequences",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.add_column(
        "document_sequences",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("document_sequences", "updated_at")
    op.drop_column("document_sequences", "created_at")
