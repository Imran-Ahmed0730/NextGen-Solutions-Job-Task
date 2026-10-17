"""Add customer collection and supplier payment documents."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

from alembic import op

revision = "20261020_party_money_docs"
down_revision = "20261019_money_txn_permissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_collections",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("doc_no", sa.String(length=50), nullable=False),
        sa.Column("doc_date", sa.Date(), nullable=False),
        sa.Column("customer_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("account_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("method_ref", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="POSTED", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", BIGINT(unsigned=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("amount > 0", name="ck_customer_collections_positive_amount"),
        sa.CheckConstraint("status = 'POSTED'", name="ck_customer_collections_posted_status"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["account_id"], ["money_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doc_no", name="uq_customer_collections_doc_no"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_customer_collections_customer_id", "customer_collections", ["customer_id"])
    op.create_index("ix_customer_collections_account_id", "customer_collections", ["account_id"])

    op.create_table(
        "supplier_payments",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("doc_no", sa.String(length=50), nullable=False),
        sa.Column("doc_date", sa.Date(), nullable=False),
        sa.Column("supplier_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("account_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="POSTED", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", BIGINT(unsigned=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("amount > 0", name="ck_supplier_payments_positive_amount"),
        sa.CheckConstraint("status = 'POSTED'", name="ck_supplier_payments_posted_status"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["account_id"], ["money_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doc_no", name="uq_supplier_payments_doc_no"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_supplier_payments_supplier_id", "supplier_payments", ["supplier_id"])
    op.create_index("ix_supplier_payments_account_id", "supplier_payments", ["account_id"])

    op.create_table(
        "payment_allocations",
        sa.Column("id", BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("payment_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("ref_type", sa.String(length=20), nullable=False),
        sa.Column("ref_id", BIGINT(unsigned=True), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.CheckConstraint(
            "ref_type IN ('RECEIPT', 'DIRECT_PURCHASE')",
            name="ck_payment_allocations_ref_type",
        ),
        sa.CheckConstraint("amount > 0", name="ck_payment_allocations_positive_amount"),
        sa.ForeignKeyConstraint(["payment_id"], ["supplier_payments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "payment_id", "ref_type", "ref_id", name="uq_payment_allocations_source"
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_payment_allocations_source", "payment_allocations", ["ref_type", "ref_id"])


def downgrade() -> None:
    op.drop_index("ix_payment_allocations_source", table_name="payment_allocations")
    op.drop_table("payment_allocations")
    op.drop_index("ix_supplier_payments_account_id", table_name="supplier_payments")
    op.drop_index("ix_supplier_payments_supplier_id", table_name="supplier_payments")
    op.drop_table("supplier_payments")
    op.drop_index("ix_customer_collections_account_id", table_name="customer_collections")
    op.drop_index("ix_customer_collections_customer_id", table_name="customer_collections")
    op.drop_table("customer_collections")
