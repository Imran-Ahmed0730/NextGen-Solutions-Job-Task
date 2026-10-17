"""Seed reusable demo master data without posting business transactions."""

import argparse
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.modules.auth.models import User
from app.modules.boms.models import BOM
from app.modules.boms.schemas import BOMCreate, BOMLineInput
from app.modules.boms.service import create_bom
from app.modules.customers import service as customer_service
from app.modules.customers.models import Customer
from app.modules.document_numbering import service as numbering_service
from app.modules.document_numbering.models import DocumentSequence
from app.modules.expense_categories import service as expense_category_service
from app.modules.expense_categories.models import ExpenseCategory
from app.modules.money_accounts import service as money_account_service
from app.modules.money_accounts.models import MoneyAccount, MoneyAccountType
from app.modules.product_categories import service as product_category_service
from app.modules.product_categories.models import ProductCategory
from app.modules.products import service as product_service
from app.modules.products.models import Product, ProductType
from app.modules.suppliers import service as supplier_service
from app.modules.suppliers.models import Supplier
from app.modules.units import service as unit_service
from app.modules.units.models import Unit
from app.modules.warehouses import service as warehouse_service
from app.modules.warehouses.models import Warehouse

DOCUMENT_SEQUENCES = (
    ("QUOTATION", "QUO-"),
    ("PURCHASE_ORDER", "PO-"),
    ("GOODS_RECEIPT", "GR-"),
    ("DIRECT_PURCHASE", "DP-"),
    ("PURCHASE_RETURN", "PR-"),
    ("SALES_ORDER", "SO-"),
    ("DELIVERY", "DN-"),
    ("INVOICE", "INV-"),
    ("SALES_RETURN", "SR-"),
    ("CUSTOMER_COLLECTION", "COL-"),
    ("SUPPLIER_PAYMENT", "PAY-"),
    ("EXPENSE", "EXP-"),
    ("INCOME", "INC-"),
    ("FUND_TRANSFER", "TRF-"),
    ("PRODUCTION_ORDER", "PROD-"),
    ("STOCK_ADJUSTMENT", "ADJ-"),
    ("STOCK_TRANSFER", "ST-"),
    ("PHYSICAL_COUNT", "PC-"),
    ("PAYROLL", "PRL-"),
)


def seed_demo_data(db: Session, actor: User) -> int:
    created = 0
    unit = db.scalar(select(Unit).where(Unit.code == "DEMO-EA"))
    if unit is None:
        unit = unit_service.create_unit(
            db, {"name": "Demo Each", "code": "DEMO-EA", "allow_decimal": True}, actor
        )
        created += 1

    category = db.scalar(select(ProductCategory).where(ProductCategory.name == "Demo Products"))
    if category is None:
        category = product_category_service.create_category(
            db, {"name": "Demo Products"}, actor
        )
        created += 1

    warehouse = db.scalar(select(Warehouse).where(Warehouse.code == "DEMO-WH"))
    if warehouse is None:
        warehouse = warehouse_service.create_warehouse(
            db, {"name": "Demo Warehouse", "code": "DEMO-WH", "is_default": True}, actor
        )
        created += 1

    supplier = db.scalar(select(Supplier).where(Supplier.code == "DEMO-SUP"))
    if supplier is None:
        supplier = supplier_service.create_supplier(
            db, {"code": "DEMO-SUP", "name": "Demo Raw Materials Supplier"}, actor
        )
        created += 1

    customer = db.scalar(select(Customer).where(Customer.code == "DEMO-CUS"))
    if customer is None:
        customer = customer_service.create_customer(
            db, {"code": "DEMO-CUS", "name": "Demo Customer"}, actor
        )
        created += 1

    expense_category = db.scalar(
        select(ExpenseCategory).where(ExpenseCategory.name == "Demo Operating Expense")
    )
    if expense_category is None:
        expense_category = expense_category_service.create_category(
            db, {"name": "Demo Operating Expense"}, actor
        )
        created += 1

    for name, account_type, opening_balance in (
        ("Demo Cash", MoneyAccountType.CASH, Decimal("1000.00")),
        ("Demo Bank", MoneyAccountType.BANK, Decimal("5000.00")),
        ("Demo MFS", MoneyAccountType.MFS, Decimal("1000.00")),
    ):
        account = db.scalar(select(MoneyAccount).where(MoneyAccount.name == name))
        if account is None:
            money_account_service.create_money_account(
                db,
                {
                    "name": name,
                    "type": account_type.value,
                    "opening_balance": opening_balance,
                },
                actor,
            )
            created += 1

    raw_product = db.scalar(select(Product).where(Product.sku == "DEMO-RAW-001"))
    if raw_product is None:
        raw_product = product_service.create_product(
            db,
            {
                "sku": "DEMO-RAW-001",
                "name": "Demo Raw Material",
                "type": ProductType.RAW,
                "category_id": category.id,
                "unit_id": unit.id,
                "is_stocked": True,
                "reorder_level": Decimal("10.000"),
            },
            actor,
        )
        created += 1

    finished_product = db.scalar(select(Product).where(Product.sku == "DEMO-FG-001"))
    if finished_product is None:
        finished_product = product_service.create_product(
            db,
            {
                "sku": "DEMO-FG-001",
                "name": "Demo Finished Product",
                "type": ProductType.FINISHED,
                "category_id": category.id,
                "unit_id": unit.id,
                "is_stocked": True,
                "sales_price_default": Decimal("20.00"),
            },
            actor,
        )
        created += 1

    bom = db.scalar(select(BOM).where(BOM.code == "DEMO-BOM-001"))
    if bom is None:
        create_bom(
            db,
            BOMCreate(
                code="DEMO-BOM-001",
                finished_product_id=finished_product.id,
                output_qty=Decimal("1.000"),
                lines=[BOMLineInput(raw_product_id=raw_product.id, qty=Decimal("2.000"))],
            ),
            actor,
        )
        created += 1

    year = datetime.now(UTC).year
    for doc_type, prefix in DOCUMENT_SEQUENCES:
        sequence = db.scalar(
            select(DocumentSequence).where(
                DocumentSequence.doc_type == doc_type,
                DocumentSequence.year == year,
            )
        )
        if sequence is None:
            numbering_service.create_sequence(
                db,
                {
                    "doc_type": doc_type,
                    "prefix": prefix,
                    "year": year,
                    "last_number": 0,
                    "padding": 4,
                },
                actor,
            )
            created += 1

    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo master data and document sequences.")
    parser.add_argument(
        "--username", default="admin", help="Existing active administrator username."
    )
    args = parser.parse_args()

    with SessionLocal() as session:
        actor = session.scalar(
            select(User).where(User.username == args.username, User.is_active.is_(True))
        )
        if actor is None:
            raise SystemExit(
                f"Active user '{args.username}' not found. "
                "Run the initial administrator seed first."
            )
        created = seed_demo_data(session, actor)

    print(f"Demo data ready. Created {created} record(s); existing demo records were preserved.")


if __name__ == "__main__":
    main()
