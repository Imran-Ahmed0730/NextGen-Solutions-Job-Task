from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.config import get_settings
from app.modules.auth.models import User
from app.modules.company_settings.models import CompanySetting  # noqa: F401
from app.modules.customers.models import Customer  # noqa: F401
from app.modules.direct_purchases.models import DirectPurchase, DirectPurchaseLine  # noqa: F401
from app.modules.document_numbering.models import DocumentSequence  # noqa: F401
from app.modules.expense_categories.models import ExpenseCategory  # noqa: F401
from app.modules.goods_receipts.models import GoodsReceipt, GoodsReceiptLine  # noqa: F401
from app.modules.income_categories.models import IncomeCategory  # noqa: F401
from app.modules.inventory.models import StockBalance, StockTransaction  # noqa: F401
from app.modules.money_accounts.models import MoneyAccount  # noqa: F401
from app.modules.money_collections.models import CustomerCollection  # noqa: F401
from app.modules.money_transactions.models import MoneyTransaction  # noqa: F401
from app.modules.parties.models import PartyContact  # noqa: F401
from app.modules.payment_methods.models import PaymentMethod  # noqa: F401
from app.modules.physical_counts.models import PhysicalCount, PhysicalCountLine  # noqa: F401
from app.modules.price_lists.models import PriceList, ProductPrice  # noqa: F401
from app.modules.product_categories.models import ProductCategory  # noqa: F401
from app.modules.products.models import Product  # noqa: F401
from app.modules.purchase_orders.models import PurchaseOrder, PurchaseOrderLine  # noqa: F401
from app.modules.purchase_returns.models import PurchaseReturn, PurchaseReturnLine  # noqa: F401
from app.modules.quotations.models import Quotation, QuotationLine  # noqa: F401
from app.modules.sales.models import (  # noqa: F401
    SalesDelivery,
    SalesDeliveryLine,
    SalesOrder,
    SalesOrderLine,
)
from app.modules.sales_invoices.models import SalesInvoice, SalesInvoiceLine  # noqa: F401
from app.modules.sales_returns.models import SalesReturn, SalesReturnLine  # noqa: F401
from app.modules.stock_adjustments.models import StockAdjustment, StockAdjustmentLine  # noqa: F401
from app.modules.stock_transfers.models import StockTransfer, StockTransferLine  # noqa: F401
from app.modules.supplier_payments.models import (  # noqa: F401
    SupplierPayment,
    SupplierPaymentAllocation,
)
from app.modules.suppliers.models import Supplier  # noqa: F401
from app.modules.units.models import Unit  # noqa: F401
from app.modules.warehouses.models import Warehouse  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = User.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
