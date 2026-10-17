from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, literal, select
from sqlalchemy.orm import Session

from app.modules.assets.models import Asset
from app.modules.attendance.models import Attendance
from app.modules.customers.models import Customer
from app.modules.direct_purchases.models import DirectPurchase, DirectPurchaseLine
from app.modules.expenses.models import Expense
from app.modules.goods_receipts.models import GoodsReceipt, GoodsReceiptLine
from app.modules.inventory.models import StockBalance
from app.modules.money_accounts.models import MoneyAccount
from app.modules.money_collections.models import CustomerCollection
from app.modules.money_transactions.models import MoneyTransaction
from app.modules.payroll.models import PayrollRun
from app.modules.production_orders.models import ProductionOrder
from app.modules.products.models import Product
from app.modules.purchase_returns.models import PurchaseReturn, PurchaseReturnLine
from app.modules.sales.models import SalesOrder, SalesOrderLine
from app.modules.sales_invoices.models import SalesInvoice, SalesInvoiceLine
from app.modules.sales_returns.models import SalesReturn, SalesReturnLine
from app.modules.supplier_payments.models import SupplierPayment
from app.modules.suppliers.models import Supplier
from app.modules.warehouses.models import Warehouse


def _decimal(value: object | None) -> Decimal:
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value))


def _sum(db: Session, statement: Select[Any]) -> Decimal:
    value = db.scalar(statement)
    return _decimal(value)


def dashboard_totals(db: Session, period_from: date, period_to: date) -> dict[str, object]:
    sales = _sum(
        db,
        select(func.coalesce(func.sum(SalesInvoice.total), 0)).where(
            SalesInvoice.doc_date >= period_from,
            SalesInvoice.doc_date <= period_to,
        ),
    )
    sales_returns = _sum(
        db,
        select(func.coalesce(func.sum(SalesReturn.total), 0)).where(
            SalesReturn.doc_date >= period_from,
            SalesReturn.doc_date <= period_to,
        ),
    )
    net_sales = sales - sales_returns

    cogs = _sum(
        db,
        select(func.coalesce(func.sum(SalesInvoice.cogs_total), 0)).where(
            SalesInvoice.doc_date >= period_from,
            SalesInvoice.doc_date <= period_to,
        ),
    )
    returned_cogs = _sum(
        db,
        select(
            func.coalesce(
                func.sum(SalesReturnLine.qty * SalesReturnLine.unit_cost_cogs), 0
            )
        )
        .join(SalesReturn, SalesReturn.id == SalesReturnLine.return_id)
        .where(SalesReturn.doc_date >= period_from, SalesReturn.doc_date <= period_to),
    )
    expenses = _sum(
        db,
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.status == "POSTED",
            Expense.doc_date >= period_from,
            Expense.doc_date <= period_to,
        ),
    )

    receipts = _sum(
        db,
        select(func.coalesce(func.sum(GoodsReceipt.total), 0)).where(
            GoodsReceipt.doc_date >= period_from,
            GoodsReceipt.doc_date <= period_to,
        ),
    )
    direct_purchases = _sum(
        db,
        select(func.coalesce(func.sum(DirectPurchase.total), 0)).where(
            DirectPurchase.doc_date >= period_from,
            DirectPurchase.doc_date <= period_to,
        ),
    )
    purchase_returns = _sum(
        db,
        select(func.coalesce(func.sum(PurchaseReturn.total), 0)).where(
            PurchaseReturn.doc_date >= period_from,
            PurchaseReturn.doc_date <= period_to,
        ),
    )

    collection_total = _sum(
        db,
        select(func.coalesce(func.sum(CustomerCollection.amount), 0)).where(
            CustomerCollection.status == "POSTED",
            CustomerCollection.doc_date >= period_from,
            CustomerCollection.doc_date <= period_to,
        ),
    )

    transaction_balances = (
        select(
            MoneyTransaction.account_id.label("account_id"),
            func.sum(MoneyTransaction.amount_signed).label("ledger_balance"),
        )
        .group_by(MoneyTransaction.account_id)
        .subquery()
    )
    balance_rows = db.execute(
        select(
            MoneyAccount.type,
            func.sum(
                MoneyAccount.opening_balance
                + func.coalesce(transaction_balances.c.ledger_balance, 0)
            ),
        )
        .outerjoin(transaction_balances, transaction_balances.c.account_id == MoneyAccount.id)
        .group_by(MoneyAccount.type)
    ).all()
    account_balances = {account_type.value: _decimal(value) for account_type, value in balance_rows}

    customer_due = (
        _sum(db, select(func.coalesce(func.sum(Customer.opening_due), 0)))
        + _sum(db, select(func.coalesce(func.sum(SalesInvoice.total), 0)))
        - _sum(
            db,
            select(func.coalesce(func.sum(CustomerCollection.amount), 0)).where(
                CustomerCollection.status == "POSTED"
            ),
        )
        - _sum(db, select(func.coalesce(func.sum(SalesReturn.total), 0)))
    )
    supplier_due = (
        _sum(db, select(func.coalesce(func.sum(Supplier.opening_due), 0)))
        + _sum(db, select(func.coalesce(func.sum(GoodsReceipt.total), 0)))
        + _sum(db, select(func.coalesce(func.sum(DirectPurchase.total), 0)))
        - _sum(
            db,
            select(func.coalesce(func.sum(SupplierPayment.amount), 0)).where(
                SupplierPayment.status == "POSTED"
            ),
        )
        - _sum(db, select(func.coalesce(func.sum(PurchaseReturn.total), 0)))
    )

    inventory_value = _sum(
        db,
        select(
            func.coalesce(
                func.sum(StockBalance.qty_on_hand * Product.avg_cost),
                0,
            )
        )
        .join(Product, Product.id == StockBalance.product_id)
        .where(Product.is_stocked.is_(True)),
    )

    remaining_order = (
        select(SalesOrderLine.id)
        .where(
            SalesOrderLine.order_id == SalesOrder.id,
            SalesOrderLine.qty_delivered < SalesOrderLine.qty_ordered,
        )
        .exists()
    )
    pending_orders = db.scalar(
        select(func.count(SalesOrder.id)).where(remaining_order)
    ) or 0

    return {
        "period_from": period_from,
        "period_to": period_to,
        "sales": net_sales,
        "collections": collection_total,
        "expenses": expenses,
        "purchases": receipts + direct_purchases - purchase_returns,
        "account_balances": account_balances,
        "customer_due": customer_due,
        "supplier_due": supplier_due,
        "inventory_value": inventory_value,
        "pending_orders": pending_orders,
        "cogs": cogs - returned_cogs,
        "estimated_profit": net_sales - cogs + returned_cogs - expenses,
    }


REPORT_TITLES = {
    "sales": "Sales",
    "purchases": "Purchases",
    "stock_valuation": "Stock valuation",
    "low_stock": "Low stock",
    "customer_due": "Customer due",
    "supplier_due": "Supplier due",
    "production_cost": "Production cost",
    "cash_book": "Cash book",
    "expense_income": "Expenses and income",
    "profit": "Profit summary",
    "assets": "Asset register",
    "attendance_payroll": "Attendance and payroll",
}


def report_options(db: Session) -> dict[str, list[dict[str, object]]]:
    return {
        "customers": [
            {"id": row.id, "label": f"{row.code} — {row.name}"}
            for row in db.scalars(
                select(Customer)
                .where(Customer.is_active.is_(True), Customer.deleted_at.is_(None))
                .order_by(Customer.name)
            )
        ],
        "suppliers": [
            {"id": row.id, "label": f"{row.code} — {row.name}"}
            for row in db.scalars(
                select(Supplier)
                .where(Supplier.is_active.is_(True), Supplier.deleted_at.is_(None))
                .order_by(Supplier.name)
            )
        ],
        "products": [
            {"id": row.id, "label": f"{row.sku} — {row.name}"}
            for row in db.scalars(
                select(Product)
                .where(Product.is_active.is_(True), Product.deleted_at.is_(None))
                .order_by(Product.name)
            )
        ],
        "warehouses": [
            {"id": row.id, "label": f"{row.code} — {row.name}"}
            for row in db.scalars(
                select(Warehouse)
                .where(Warehouse.is_active.is_(True), Warehouse.deleted_at.is_(None))
                .order_by(Warehouse.name)
            )
        ],
    }


def _rows(db: Session, statement: Select[Any]) -> list[dict[str, object]]:
    return [dict(row) for row in db.execute(statement).mappings().all()]


def report_data(
    db: Session,
    report_type: str,
    period_from: date,
    period_to: date,
    warehouse_id: int | None = None,
    party_id: int | None = None,
    product_id: int | None = None,
) -> list[dict[str, object]]:
    if report_type == "sales":
        invoice_filters = [
            SalesInvoice.doc_date >= period_from,
            SalesInvoice.doc_date <= period_to,
        ]
        return_filters = [
            SalesReturn.doc_date >= period_from,
            SalesReturn.doc_date <= period_to,
        ]
        if party_id is not None:
            invoice_filters.append(SalesInvoice.customer_id == party_id)
            return_filters.append(SalesReturn.customer_id == party_id)
        if product_id is not None:
            invoice_filters.append(
                SalesInvoice.id.in_(
                    select(SalesInvoiceLine.invoice_id).where(
                        SalesInvoiceLine.product_id == product_id
                    )
                )
            )
            return_filters.append(
                SalesReturn.id.in_(
                    select(SalesReturnLine.return_id).where(
                        SalesReturnLine.product_id == product_id
                    )
                )
            )
        invoice_rows = _rows(
            db,
            select(
                SalesInvoice.doc_date.label("date"),
                SalesInvoice.doc_no.label("document"),
                Customer.name.label("party"),
                SalesInvoice.total.label("amount"),
                SalesInvoice.cogs_total.label("cogs"),
                literal("Invoice").label("type"),
            )
            .join(Customer, Customer.id == SalesInvoice.customer_id)
            .where(*invoice_filters),
        )
        return_rows = _rows(
            db,
            select(
                SalesReturn.doc_date.label("date"),
                SalesReturn.doc_no.label("document"),
                Customer.name.label("party"),
                (-SalesReturn.total).label("amount"),
                (
                    -func.coalesce(
                        func.sum(SalesReturnLine.qty * SalesReturnLine.unit_cost_cogs), 0
                    )
                ).label("cogs"),
                literal("Return").label("type"),
            )
            .join(Customer, Customer.id == SalesReturn.customer_id)
            .join(SalesReturnLine, SalesReturnLine.return_id == SalesReturn.id)
            .where(*return_filters)
            .group_by(SalesReturn.id, Customer.name),
        )
        return sorted(
            invoice_rows + return_rows,
            key=lambda row: (str(row["date"]), str(row["document"])),
        )

    if report_type == "purchases":
        receipt_filters = [
            GoodsReceipt.doc_date >= period_from,
            GoodsReceipt.doc_date <= period_to,
        ]
        direct_filters = [
            DirectPurchase.doc_date >= period_from,
            DirectPurchase.doc_date <= period_to,
        ]
        purchase_return_filters = [
            PurchaseReturn.doc_date >= period_from,
            PurchaseReturn.doc_date <= period_to,
        ]
        if party_id is not None:
            receipt_filters.append(GoodsReceipt.supplier_id == party_id)
            direct_filters.append(DirectPurchase.supplier_id == party_id)
            purchase_return_filters.append(PurchaseReturn.supplier_id == party_id)
        if product_id is not None:
            receipt_filters.append(
                GoodsReceipt.id.in_(
                    select(GoodsReceiptLine.receipt_id).where(
                        GoodsReceiptLine.product_id == product_id
                    )
                )
            )
            direct_filters.append(
                DirectPurchase.id.in_(
                    select(DirectPurchaseLine.purchase_id).where(
                        DirectPurchaseLine.product_id == product_id
                    )
                )
            )
            purchase_return_filters.append(
                PurchaseReturn.id.in_(
                    select(PurchaseReturnLine.return_id).where(
                        PurchaseReturnLine.product_id == product_id
                    )
                )
            )
        receipt_rows = _rows(
            db,
            select(
                GoodsReceipt.doc_date.label("date"),
                GoodsReceipt.doc_no.label("document"),
                Supplier.name.label("party"),
                GoodsReceipt.total.label("amount"),
                literal("Goods receipt").label("type"),
            )
            .join(Supplier, Supplier.id == GoodsReceipt.supplier_id)
            .where(*receipt_filters),
        )
        direct_rows = _rows(
            db,
            select(
                DirectPurchase.doc_date.label("date"),
                DirectPurchase.doc_no.label("document"),
                Supplier.name.label("party"),
                DirectPurchase.total.label("amount"),
                literal("Direct purchase").label("type"),
            )
            .join(Supplier, Supplier.id == DirectPurchase.supplier_id)
            .where(*direct_filters),
        )
        return_rows = _rows(
            db,
            select(
                PurchaseReturn.doc_date.label("date"),
                PurchaseReturn.doc_no.label("document"),
                Supplier.name.label("party"),
                (-PurchaseReturn.total).label("amount"),
                literal("Purchase return").label("type"),
            )
            .join(Supplier, Supplier.id == PurchaseReturn.supplier_id)
            .where(*purchase_return_filters),
        )
        return sorted(
            receipt_rows + direct_rows + return_rows,
            key=lambda row: (str(row["date"]), str(row["document"])),
        )

    if report_type in {"stock_valuation", "low_stock"}:
        statement = (
            select(
                Product.sku.label("sku"),
                Product.name.label("product"),
                func.coalesce(func.sum(StockBalance.qty_on_hand), 0).label("on_hand"),
                Product.reorder_level.label("reorder_level"),
                Product.avg_cost.label("unit_cost"),
                (
                    func.coalesce(func.sum(StockBalance.qty_on_hand), 0) * Product.avg_cost
                ).label("value"),
            )
            .outerjoin(
                StockBalance,
                (StockBalance.product_id == Product.id)
                & (
                    (StockBalance.warehouse_id == warehouse_id)
                    if warehouse_id is not None
                    else True
                ),
            )
            .where(
                Product.is_stocked.is_(True),
            )
            .group_by(Product.id)
            .order_by(Product.name)
        )
        if report_type == "low_stock":
            statement = statement.having(
                func.coalesce(func.sum(StockBalance.qty_on_hand), 0) <= Product.reorder_level
            ).where(Product.is_active.is_(True), Product.deleted_at.is_(None))
        if product_id is not None:
            statement = statement.where(Product.id == product_id)
        return _rows(db, statement)

    if report_type in {"customer_due", "supplier_due"}:
        if report_type == "customer_due":
            open_balances = {party.id: party.opening_due for party in db.scalars(select(Customer))}
            additions = db.execute(
                select(SalesInvoice.customer_id, func.sum(SalesInvoice.total))
                .where(SalesInvoice.doc_date <= period_to)
                .group_by(SalesInvoice.customer_id)
            ).all()
            reductions = db.execute(
                select(CustomerCollection.customer_id, func.sum(CustomerCollection.amount))
                .where(
                    CustomerCollection.status == "POSTED",
                    CustomerCollection.doc_date <= period_to,
                )
                .group_by(CustomerCollection.customer_id)
            ).all()
            returned = db.execute(
                select(SalesReturn.customer_id, func.sum(SalesReturn.total))
                .where(SalesReturn.doc_date <= period_to)
                .group_by(SalesReturn.customer_id)
            ).all()
            for customer_id, amount in additions:
                open_balances[customer_id] += _decimal(amount)
            for customer_id, amount in reductions:
                open_balances[customer_id] -= _decimal(amount)
            for customer_id, amount in returned:
                open_balances[customer_id] -= _decimal(amount)
            customer_query = select(Customer).order_by(Customer.name)
            if party_id is not None:
                customer_query = customer_query.where(Customer.id == party_id)
            return [
                {"code": party.code, "party": party.name, "due": open_balances[party.id]}
                for party in db.scalars(customer_query)
            ]

        open_balances = {party.id: party.opening_due for party in db.scalars(select(Supplier))}
        purchase_statements: tuple[Select[Any], ...] = (
            select(GoodsReceipt.supplier_id, func.sum(GoodsReceipt.total))
            .where(GoodsReceipt.doc_date <= period_to)
            .group_by(GoodsReceipt.supplier_id),
            select(DirectPurchase.supplier_id, func.sum(DirectPurchase.total))
            .where(DirectPurchase.doc_date <= period_to)
            .group_by(DirectPurchase.supplier_id),
        )
        for purchase_statement in purchase_statements:
            for supplier_id, amount in db.execute(purchase_statement).all():
                open_balances[supplier_id] += _decimal(amount)
        reduction_statements: tuple[Select[Any], ...] = (
            select(SupplierPayment.supplier_id, func.sum(SupplierPayment.amount))
            .where(
                SupplierPayment.status == "POSTED",
                SupplierPayment.doc_date <= period_to,
            )
            .group_by(SupplierPayment.supplier_id),
            select(PurchaseReturn.supplier_id, func.sum(PurchaseReturn.total))
            .where(PurchaseReturn.doc_date <= period_to)
            .group_by(PurchaseReturn.supplier_id),
        )
        for reduction_statement in reduction_statements:
            for supplier_id, amount in db.execute(reduction_statement).all():
                open_balances[supplier_id] -= _decimal(amount)
        supplier_query = select(Supplier).order_by(Supplier.name)
        if party_id is not None:
            supplier_query = supplier_query.where(Supplier.id == party_id)
        return [
            {"code": party.code, "party": party.name, "due": open_balances[party.id]}
            for party in db.scalars(supplier_query)
        ]

    if report_type == "production_cost":
        production_filters = [
            ProductionOrder.doc_date >= period_from,
            ProductionOrder.doc_date <= period_to,
            ProductionOrder.status == "COMPLETED",
        ]
        if product_id is not None:
            production_filters.append(ProductionOrder.finished_product_id == product_id)
        if warehouse_id is not None:
            production_filters.append(ProductionOrder.warehouse_id == warehouse_id)
        return _rows(
            db,
            select(
                ProductionOrder.doc_date.label("date"),
                ProductionOrder.doc_no.label("document"),
                ProductionOrder.status.label("status"),
                ProductionOrder.actual_qty.label("output_qty"),
                ProductionOrder.material_cost.label("material_cost"),
                ProductionOrder.labor_cost.label("labor_cost"),
                ProductionOrder.overhead_cost.label("overhead_cost"),
                ProductionOrder.total_cost.label("total_cost"),
                ProductionOrder.unit_cost.label("unit_cost"),
            )
            .where(*production_filters)
            .order_by(ProductionOrder.doc_date, ProductionOrder.id),
        )

    if report_type == "cash_book":
        return _rows(
            db,
            select(
                MoneyTransaction.txn_date.label("date"),
                MoneyAccount.name.label("account"),
                MoneyTransaction.txn_type.label("type"),
                MoneyTransaction.source_type.label("source"),
                MoneyTransaction.source_id.label("source_id"),
                MoneyTransaction.amount_signed.label("amount"),
                MoneyTransaction.note.label("note"),
            )
            .join(MoneyAccount, MoneyAccount.id == MoneyTransaction.account_id)
            .where(
                func.date(MoneyTransaction.txn_date) >= period_from,
                func.date(MoneyTransaction.txn_date) <= period_to,
            )
            .order_by(MoneyTransaction.txn_date, MoneyTransaction.id),
        )

    if report_type == "expense_income":
        from app.modules.incomes.models import Income

        expense_rows = _rows(
            db,
            select(
                Expense.doc_date.label("date"),
                Expense.doc_no.label("document"),
                Expense.amount.label("amount"),
                literal("Expense").label("type"),
            ).where(
                Expense.status == "POSTED",
                Expense.doc_date >= period_from,
                Expense.doc_date <= period_to,
            ),
        )
        income_rows = _rows(
            db,
            select(
                Income.doc_date.label("date"),
                Income.doc_no.label("document"),
                Income.amount.label("amount"),
                literal("Income").label("type"),
            ).where(
                Income.status == "POSTED",
                Income.doc_date >= period_from,
                Income.doc_date <= period_to,
            ),
        )
        return sorted(
            expense_rows + income_rows,
            key=lambda row: (str(row["date"]), str(row["document"])),
        )

    if report_type == "profit":
        values = dashboard_totals(db, period_from, period_to)
        return [
            {
                "sales": values["sales"],
                "cogs": values["cogs"],
                "expenses": values["expenses"],
                "estimated_profit": values["estimated_profit"],
            }
        ]

    if report_type == "assets":
        return _rows(
            db,
            select(
                Asset.asset_code.label("asset_code"),
                Asset.name.label("asset"),
                Asset.category.label("category"),
                Asset.purchase_date.label("purchase_date"),
                Asset.purchase_cost.label("purchase_cost"),
                Asset.location.label("location"),
                Asset.status.label("status"),
            )
            .where(Asset.is_active.is_(True))
            .order_by(Asset.asset_code),
        )

    if report_type == "attendance_payroll":
        attendance = _rows(
            db,
            select(
                Attendance.att_date.label("date"),
                Attendance.status.label("status"),
                func.count(Attendance.id).label("employee_count"),
            )
            .where(Attendance.att_date >= period_from, Attendance.att_date <= period_to)
            .group_by(Attendance.att_date, Attendance.status)
            .order_by(Attendance.att_date, Attendance.status),
        )
        payroll = _rows(
            db,
            select(
                PayrollRun.period_year.label("year"),
                PayrollRun.period_month.label("month"),
                PayrollRun.doc_no.label("document"),
                PayrollRun.status.label("status"),
                PayrollRun.total_amount.label("total_amount"),
            )
            .where(
                PayrollRun.paid_on >= period_from,
                PayrollRun.paid_on <= period_to,
            )
            .order_by(PayrollRun.paid_on, PayrollRun.id),
        )
        return attendance + payroll

    return []
