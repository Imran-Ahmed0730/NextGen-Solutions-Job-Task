"""Create the append-only money transaction ledger."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

from alembic import op

revision = "20261018_money_transactions"
down_revision = "20261017_pr_permissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "money_transactions",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column(
            "txn_date",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("account_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("amount_signed", sa.Numeric(18, 2), nullable=False),
        sa.Column(
            "txn_type",
            sa.Enum(
                "COLLECTION",
                "PAYMENT",
                "EXPENSE",
                "INCOME",
                "TRANSFER_OUT",
                "TRANSFER_IN",
                "OPENING",
                "PURCHASE_PAYMENT",
                "SALARY",
                native_enum=False,
                length=30,
                create_constraint=True,
                name="ck_money_transactions_txn_type",
            ),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(length=50), nullable=True),
        sa.Column("source_id", BIGINT(unsigned=True), nullable=True),
        sa.Column("party_type", sa.String(length=20), nullable=True),
        sa.Column("party_id", BIGINT(unsigned=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", BIGINT(unsigned=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "amount_signed <> 0",
            name="ck_money_transactions_nonzero_amount",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["money_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_money_transactions_account_date",
        "money_transactions",
        ["account_id", "txn_date"],
    )
    op.create_index(
        "ix_money_transactions_source",
        "money_transactions",
        ["source_type", "source_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_money_transactions_source", table_name="money_transactions")
    op.drop_index("ix_money_transactions_account_date", table_name="money_transactions")
    op.drop_table("money_transactions")
