"""Create read-only reporting views."""

from alembic import op

revision = "20261111_reporting_views"
down_revision = "20261110_reports_dashboard"
branch_labels = None
depends_on = None

VIEWS = {
    "v_current_stock": """
        SELECT
            balances.product_id,
            products.sku,
            products.name AS product_name,
            balances.warehouse_id,
            warehouses.code AS warehouse_code,
            warehouses.name AS warehouse_name,
            balances.qty_on_hand,
            balances.qty_reserved,
            balances.qty_on_hand - balances.qty_reserved AS qty_available,
            products.avg_cost,
            balances.qty_on_hand * products.avg_cost AS inventory_value
        FROM stock_balances AS balances
        JOIN products ON products.id = balances.product_id
        JOIN warehouses ON warehouses.id = balances.warehouse_id
    """,
    "v_stock_valuation": """
        SELECT
            products.id AS product_id,
            products.sku,
            products.name AS product_name,
            products.reorder_level,
            products.avg_cost,
            COALESCE(stock.qty_on_hand, 0) AS qty_on_hand,
            COALESCE(stock.qty_reserved, 0) AS qty_reserved,
            COALESCE(stock.qty_on_hand, 0) - COALESCE(stock.qty_reserved, 0) AS qty_available,
            COALESCE(stock.qty_on_hand, 0) * products.avg_cost AS inventory_value
        FROM products
        LEFT JOIN (
            SELECT
                product_id,
                SUM(qty_on_hand) AS qty_on_hand,
                SUM(qty_reserved) AS qty_reserved
            FROM stock_balances
            GROUP BY product_id
        ) AS stock ON stock.product_id = products.id
        WHERE products.is_stocked = 1
    """,
    "v_low_stock": """
        SELECT
            valuation.product_id,
            valuation.sku,
            valuation.product_name,
            valuation.qty_on_hand,
            valuation.reorder_level,
            valuation.avg_cost,
            valuation.inventory_value
        FROM v_stock_valuation AS valuation
        JOIN products ON products.id = valuation.product_id
        WHERE products.is_active = 1
          AND products.deleted_at IS NULL
          AND valuation.qty_on_hand <= valuation.reorder_level
    """,
    "v_customer_due": """
        SELECT
            customers.id AS customer_id,
            customers.code,
            customers.name,
            customers.opening_due
                + COALESCE(invoices.total, 0)
                - COALESCE(collections.total, 0)
                - COALESCE(returns.total, 0) AS due
        FROM customers
        LEFT JOIN (
            SELECT customer_id, SUM(total) AS total
            FROM invoices
            WHERE status = 'POSTED'
            GROUP BY customer_id
        ) AS invoices ON invoices.customer_id = customers.id
        LEFT JOIN (
            SELECT customer_id, SUM(amount) AS total
            FROM customer_collections
            WHERE status = 'POSTED'
            GROUP BY customer_id
        ) AS collections ON collections.customer_id = customers.id
        LEFT JOIN (
            SELECT customer_id, SUM(total) AS total
            FROM sales_returns
            WHERE status = 'POSTED'
            GROUP BY customer_id
        ) AS returns ON returns.customer_id = customers.id
    """,
    "v_supplier_due": """
        SELECT
            suppliers.id AS supplier_id,
            suppliers.code,
            suppliers.name,
            suppliers.opening_due
                + COALESCE(receipts.total, 0)
                + COALESCE(direct_purchases.total, 0)
                - COALESCE(payments.total, 0)
                - COALESCE(returns.total, 0) AS due
        FROM suppliers
        LEFT JOIN (
            SELECT supplier_id, SUM(total) AS total
            FROM goods_receipts
            WHERE status = 'POSTED'
            GROUP BY supplier_id
        ) AS receipts ON receipts.supplier_id = suppliers.id
        LEFT JOIN (
            SELECT supplier_id, SUM(total) AS total
            FROM direct_purchases
            WHERE status = 'POSTED'
            GROUP BY supplier_id
        ) AS direct_purchases ON direct_purchases.supplier_id = suppliers.id
        LEFT JOIN (
            SELECT supplier_id, SUM(amount) AS total
            FROM supplier_payments
            WHERE status = 'POSTED'
            GROUP BY supplier_id
        ) AS payments ON payments.supplier_id = suppliers.id
        LEFT JOIN (
            SELECT supplier_id, SUM(total) AS total
            FROM purchase_returns
            WHERE status = 'POSTED'
            GROUP BY supplier_id
        ) AS returns ON returns.supplier_id = suppliers.id
    """,
    "v_account_balance": """
        SELECT
            accounts.id AS account_id,
            accounts.name AS account_name,
            accounts.type AS account_type,
            accounts.opening_balance
                + COALESCE(transactions.ledger_total, 0) AS balance
        FROM money_accounts AS accounts
        LEFT JOIN (
            SELECT account_id, SUM(amount_signed) AS ledger_total
            FROM money_transactions
            GROUP BY account_id
        ) AS transactions ON transactions.account_id = accounts.id
    """,
    "v_order_status": """
        SELECT
            orders.id AS order_id,
            orders.doc_no,
            orders.doc_date,
            orders.customer_id,
            orders.warehouse_id,
            orders.status,
            order_lines.id AS order_line_id,
            order_lines.product_id,
            order_lines.qty_ordered,
            order_lines.qty_reserved,
            order_lines.qty_produced,
            order_lines.qty_delivered,
            order_lines.qty_ordered - order_lines.qty_delivered AS qty_remaining
        FROM sales_orders AS orders
        JOIN sales_order_lines AS order_lines ON order_lines.order_id = orders.id
    """,
    "v_profit_summary": """
        SELECT
            activity.activity_date,
            SUM(activity.sales) AS sales,
            SUM(activity.cogs) AS cogs,
            SUM(activity.expenses) AS expenses,
            SUM(activity.sales) - SUM(activity.cogs) - SUM(activity.expenses)
                AS estimated_profit
        FROM (
            SELECT
                doc_date AS activity_date,
                total AS sales,
                cogs_total AS cogs,
                0 AS expenses
            FROM invoices
            WHERE status = 'POSTED'
            UNION ALL
            SELECT
                returns.doc_date AS activity_date,
                -returns.total AS sales,
                -COALESCE(return_lines.cogs, 0) AS cogs,
                0 AS expenses
            FROM sales_returns AS returns
            LEFT JOIN (
                SELECT
                    return_id,
                    SUM(qty * unit_cost_cogs) AS cogs
                FROM sales_return_lines
                GROUP BY return_id
            ) AS return_lines ON return_lines.return_id = returns.id
            WHERE returns.status = 'POSTED'
            UNION ALL
            SELECT
                doc_date AS activity_date,
                0 AS sales,
                0 AS cogs,
                amount AS expenses
            FROM expenses
            WHERE status = 'POSTED'
        ) AS activity
        GROUP BY activity.activity_date
    """,
    "v_dashboard_kpis": """
        SELECT
            dates.activity_date,
            COALESCE(profit.sales, 0) AS sales,
            COALESCE(collections.total, 0) AS collections,
            COALESCE(profit.expenses, 0) AS expenses,
            COALESCE(purchases.total, 0) AS purchases,
            COALESCE((
                SELECT SUM(CASE WHEN account_type = 'CASH' THEN balance ELSE 0 END)
                FROM v_account_balance
            ), 0) AS cash_balance,
            COALESCE((
                SELECT SUM(CASE WHEN account_type = 'BANK' THEN balance ELSE 0 END)
                FROM v_account_balance
            ), 0) AS bank_balance,
            COALESCE((
                SELECT SUM(CASE WHEN account_type = 'MFS' THEN balance ELSE 0 END)
                FROM v_account_balance
            ), 0) AS mfs_balance,
            COALESCE((SELECT SUM(due) FROM v_customer_due), 0) AS customer_due,
            COALESCE((SELECT SUM(due) FROM v_supplier_due), 0) AS supplier_due,
            COALESCE((SELECT SUM(inventory_value) FROM v_stock_valuation), 0)
                AS inventory_value,
            (
                SELECT COUNT(DISTINCT order_id)
                FROM v_order_status
                WHERE qty_remaining > 0
            ) AS pending_orders,
            COALESCE(profit.estimated_profit, 0) AS estimated_profit
        FROM (
            SELECT doc_date AS activity_date FROM invoices
            UNION
            SELECT doc_date FROM sales_returns
            UNION
            SELECT doc_date FROM customer_collections
            UNION
            SELECT doc_date FROM expenses WHERE status = 'POSTED'
            UNION
            SELECT doc_date FROM goods_receipts
            UNION
            SELECT doc_date FROM direct_purchases
            UNION
            SELECT doc_date FROM purchase_returns
            UNION
            SELECT CURRENT_DATE
        ) AS dates
        LEFT JOIN v_profit_summary AS profit
            ON profit.activity_date = dates.activity_date
        LEFT JOIN (
            SELECT doc_date, SUM(amount) AS total
            FROM customer_collections
            WHERE status = 'POSTED'
            GROUP BY doc_date
        ) AS collections ON collections.doc_date = dates.activity_date
        LEFT JOIN (
            SELECT activity_date, SUM(amount) AS total
            FROM (
                SELECT doc_date AS activity_date, total AS amount
                FROM goods_receipts
                WHERE status = 'POSTED'
                UNION ALL
                SELECT doc_date, total
                FROM direct_purchases
                WHERE status = 'POSTED'
                UNION ALL
                SELECT doc_date, -total
                FROM purchase_returns
                WHERE status = 'POSTED'
            ) AS purchase_events
            GROUP BY activity_date
        ) AS purchases ON purchases.activity_date = dates.activity_date
    """,
}


def upgrade() -> None:
    for name in reversed(VIEWS):
        op.execute(f"DROP VIEW IF EXISTS {name}")
    algorithm = "ALGORITHM=TEMPTABLE " if op.get_bind().dialect.name == "mysql" else ""
    for name, query in VIEWS.items():
        op.execute(f"CREATE {algorithm}VIEW {name} AS {query}")


def downgrade() -> None:
    for name in reversed(VIEWS):
        op.execute(f"DROP VIEW IF EXISTS {name}")
