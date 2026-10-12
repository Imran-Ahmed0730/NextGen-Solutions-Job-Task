"""Initial empty migration

Revision ID: 20261012_initial_empty
Revises:
Create Date: 2026-10-12 21:00:00.000000
"""

# revision identifiers, used by Alembic.
revision = "20261012_initial_empty"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Intentionally empty; schema will be added in future modules.
    pass


def downgrade() -> None:
    pass
