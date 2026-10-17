"""add report query indexes

Revision ID: 318177480193
Revises: 20261111_reporting_views
Create Date: 2026-10-17 16:25:41.134887
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "318177480193"
down_revision = "20261111_reporting_views"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_invoices_doc_date", "invoices", ["doc_date"], unique=False)
    op.create_index("ix_sales_returns_doc_date", "sales_returns", ["doc_date"], unique=False)
    op.create_index(
        "ix_customer_collections_doc_date", "customer_collections", ["doc_date"], unique=False
    )
    op.create_index("ix_goods_receipts_doc_date", "goods_receipts", ["doc_date"], unique=False)
    op.create_index("ix_direct_purchases_doc_date", "direct_purchases", ["doc_date"], unique=False)
    op.create_index("ix_purchase_returns_doc_date", "purchase_returns", ["doc_date"], unique=False)
    op.create_index(
        "ix_supplier_payments_doc_date", "supplier_payments", ["doc_date"], unique=False
    )
    op.create_index("ix_expenses_status_doc_date", "expenses", ["status", "doc_date"], unique=False)
    op.create_index("ix_incomes_doc_date", "incomes", ["doc_date"], unique=False)
    op.create_index(
        "ix_production_orders_status_doc_date",
        "production_orders",
        ["status", "doc_date"],
        unique=False,
    )
    op.create_index("ix_attendance_att_date", "attendance", ["att_date"], unique=False)
    op.create_index("ix_payroll_runs_paid_on", "payroll_runs", ["paid_on"], unique=False)
    op.create_index(
        "ix_money_transactions_txn_date", "money_transactions", ["txn_date"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_money_transactions_txn_date", table_name="money_transactions")
    op.drop_index("ix_payroll_runs_paid_on", table_name="payroll_runs")
    op.drop_index("ix_attendance_att_date", table_name="attendance")
    op.drop_index("ix_production_orders_status_doc_date", table_name="production_orders")
    op.drop_index("ix_incomes_doc_date", table_name="incomes")
    op.drop_index("ix_expenses_status_doc_date", table_name="expenses")
    op.drop_index("ix_supplier_payments_doc_date", table_name="supplier_payments")
    op.drop_index("ix_purchase_returns_doc_date", table_name="purchase_returns")
    op.drop_index("ix_direct_purchases_doc_date", table_name="direct_purchases")
    op.drop_index("ix_goods_receipts_doc_date", table_name="goods_receipts")
    op.drop_index("ix_customer_collections_doc_date", table_name="customer_collections")
    op.drop_index("ix_sales_returns_doc_date", table_name="sales_returns")
    op.drop_index("ix_invoices_doc_date", table_name="invoices")
