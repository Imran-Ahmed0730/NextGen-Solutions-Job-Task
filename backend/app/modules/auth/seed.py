import argparse
import secrets
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import hash_password, password_hash
from app.modules.auth.models import Permission, Role, User

ADMIN_ROLE_NAME = "Administrator"
PASSWORD_HASH = password_hash


@dataclass(frozen=True)
class PermissionDefinition:
    code: str
    module: str
    description: str


@dataclass(frozen=True)
class SeedResult:
    username: str
    created: bool
    password: Optional[str]


ADMIN_PERMISSION_CATALOG = (
    PermissionDefinition("auth.profile.read", "auth", "View own profile"),
    PermissionDefinition("auth.profile.update", "auth", "Update own profile"),
    PermissionDefinition("auth.password.change", "auth", "Change own password"),
    PermissionDefinition("auth.session.logout", "auth", "End own session"),
    PermissionDefinition("auth.users.read", "auth", "View users"),
    PermissionDefinition("auth.users.create", "auth", "Create users"),
    PermissionDefinition("auth.users.update", "auth", "Update users"),
    PermissionDefinition("auth.users.delete", "auth", "Deactivate users"),
    PermissionDefinition("auth.roles.read", "auth", "View roles"),
    PermissionDefinition("auth.roles.create", "auth", "Create roles"),
    PermissionDefinition("auth.roles.update", "auth", "Update roles"),
    PermissionDefinition("auth.roles.delete", "auth", "Deactivate roles"),
    PermissionDefinition("auth.permissions.read", "auth", "View permission catalog"),
    PermissionDefinition("auth.audit_logs.read", "auth", "View audit logs"),
    PermissionDefinition("master_data.units.read", "master_data", "View units"),
    PermissionDefinition("master_data.units.create", "master_data", "Create units"),
    PermissionDefinition("master_data.units.update", "master_data", "Update units"),
    PermissionDefinition("master_data.units.delete", "master_data", "Delete units"),
    PermissionDefinition(
        "master_data.product_categories.read", "master_data", "View product categories"
    ),
    PermissionDefinition(
        "master_data.product_categories.create", "master_data", "Create product categories"
    ),
    PermissionDefinition(
        "master_data.product_categories.update", "master_data", "Update product categories"
    ),
    PermissionDefinition(
        "master_data.product_categories.delete", "master_data", "Delete product categories"
    ),
    PermissionDefinition("master_data.products.read", "master_data", "View products"),
    PermissionDefinition("master_data.products.create", "master_data", "Create products"),
    PermissionDefinition("master_data.products.update", "master_data", "Update products"),
    PermissionDefinition("master_data.products.delete", "master_data", "Delete products"),
    PermissionDefinition("master_data.warehouses.read", "master_data", "View warehouses"),
    PermissionDefinition("master_data.warehouses.create", "master_data", "Create warehouses"),
    PermissionDefinition("master_data.warehouses.update", "master_data", "Update warehouses"),
    PermissionDefinition("master_data.warehouses.delete", "master_data", "Delete warehouses"),
    PermissionDefinition(
        "master_data.expense_categories.read", "master_data", "View expense categories"
    ),
    PermissionDefinition(
        "master_data.expense_categories.create", "master_data", "Create expense categories"
    ),
    PermissionDefinition(
        "master_data.expense_categories.update", "master_data", "Update expense categories"
    ),
    PermissionDefinition(
        "master_data.expense_categories.delete", "master_data", "Delete expense categories"
    ),
    PermissionDefinition(
        "master_data.income_categories.read", "master_data", "View income categories"
    ),
    PermissionDefinition(
        "master_data.income_categories.create", "master_data", "Create income categories"
    ),
    PermissionDefinition(
        "master_data.income_categories.update", "master_data", "Update income categories"
    ),
    PermissionDefinition(
        "master_data.income_categories.delete", "master_data", "Delete income categories"
    ),
    PermissionDefinition("master_data.payment_methods.read", "master_data", "View payment methods"),
    PermissionDefinition(
        "master_data.payment_methods.create", "master_data", "Create payment methods"
    ),
    PermissionDefinition(
        "master_data.payment_methods.update", "master_data", "Update payment methods"
    ),
    PermissionDefinition(
        "master_data.payment_methods.delete", "master_data", "Delete payment methods"
    ),
    PermissionDefinition("master_data.money_accounts.read", "master_data", "View money accounts"),
    PermissionDefinition(
        "master_data.money_accounts.create", "master_data", "Create money accounts"
    ),
    PermissionDefinition(
        "master_data.money_accounts.update", "master_data", "Update money accounts"
    ),
    PermissionDefinition(
        "master_data.money_accounts.delete", "master_data", "Delete money accounts"
    ),
    PermissionDefinition("money.transactions.read", "money", "View money account balances"),
    PermissionDefinition("money.collections.read", "money", "View customer collections"),
    PermissionDefinition("money.collections.create", "money", "Post customer collections"),
    PermissionDefinition("money.supplier_payments.read", "money", "View supplier payments"),
    PermissionDefinition("money.supplier_payments.create", "money", "Post supplier payments"),
    PermissionDefinition("money.expenses.read", "money", "View expenses"),
    PermissionDefinition("money.expenses.create", "money", "Create expenses"),
    PermissionDefinition("money.incomes.read", "money", "View incomes"),
    PermissionDefinition("money.incomes.create", "money", "Create incomes"),
    PermissionDefinition("money.transfers.read", "money", "View fund transfers"),
    PermissionDefinition("money.transfers.create", "money", "Create fund transfers"),
    PermissionDefinition("sales.quotations.read", "sales", "View quotations"),
    PermissionDefinition("sales.quotations.create", "sales", "Create quotations"),
    PermissionDefinition("sales.quotations.update", "sales", "Update draft quotations"),
    PermissionDefinition("sales.orders.read", "sales", "View sales orders"),
    PermissionDefinition("sales.orders.create", "sales", "Create sales orders"),
    PermissionDefinition("sales.orders.update", "sales", "Update draft sales orders"),
    PermissionDefinition(
        "sales.orders.reserve", "sales", "Reserve and release sales order stock"
    ),
    PermissionDefinition("sales.deliveries.create", "sales", "Post sales deliveries"),
    PermissionDefinition("sales.invoices.read", "sales", "View sales invoices"),
    PermissionDefinition("sales.invoices.create", "sales", "Post sales invoices"),
    PermissionDefinition("sales.returns.read", "sales", "View sales returns"),
    PermissionDefinition("sales.returns.create", "sales", "Post sales returns"),
    PermissionDefinition("production.boms.read", "production", "View bills of materials"),
    PermissionDefinition("production.boms.create", "production", "Create bills of materials"),
    PermissionDefinition("production.boms.update", "production", "Update bills of materials"),
    PermissionDefinition("production.boms.delete", "production", "Delete bills of materials"),
    PermissionDefinition("production.orders.read", "production", "View production orders"),
    PermissionDefinition("production.orders.create", "production", "Create production orders"),
    PermissionDefinition(
        "production.orders.update", "production", "Update and post production orders"
    ),
    PermissionDefinition("master_data.price_lists.read", "master_data", "View price lists"),
    PermissionDefinition("master_data.price_lists.create", "master_data", "Create price lists"),
    PermissionDefinition("master_data.price_lists.update", "master_data", "Update price lists"),
    PermissionDefinition("master_data.price_lists.delete", "master_data", "Delete price lists"),
    PermissionDefinition(
        "master_data.company_settings.read", "master_data", "View company settings"
    ),
    PermissionDefinition(
        "master_data.company_settings.create", "master_data", "Create company settings"
    ),
    PermissionDefinition(
        "master_data.company_settings.update", "master_data", "Update company settings"
    ),
    PermissionDefinition(
        "master_data.company_settings.delete", "master_data", "Delete company settings"
    ),
    PermissionDefinition(
        "master_data.document_numbering.read", "master_data", "View document numbering"
    ),
    PermissionDefinition(
        "master_data.document_numbering.create", "master_data", "Create document numbering"
    ),
    PermissionDefinition(
        "master_data.document_numbering.update", "master_data", "Update document numbering"
    ),
    PermissionDefinition(
        "master_data.document_numbering.delete", "master_data", "Delete document numbering"
    ),
    PermissionDefinition("master_data.customers.read", "master_data", "View customers"),
    PermissionDefinition("master_data.customers.create", "master_data", "Create customers"),
    PermissionDefinition("master_data.customers.update", "master_data", "Update customers"),
    PermissionDefinition("master_data.customers.delete", "master_data", "Delete customers"),
    PermissionDefinition("master_data.suppliers.read", "master_data", "View suppliers"),
    PermissionDefinition("master_data.suppliers.create", "master_data", "Create suppliers"),
    PermissionDefinition("master_data.suppliers.update", "master_data", "Update suppliers"),
    PermissionDefinition("master_data.suppliers.delete", "master_data", "Delete suppliers"),
    PermissionDefinition(
        "inventory.stock.read", "inventory", "View current stock and stock ledger"
    ),
    PermissionDefinition("inventory.transfers.read", "inventory", "View stock transfers"),
    PermissionDefinition("inventory.transfers.create", "inventory", "Post stock transfers"),
    PermissionDefinition("inventory.adjustments.read", "inventory", "View stock adjustments"),
    PermissionDefinition("inventory.adjustments.create", "inventory", "Post stock adjustments"),
    PermissionDefinition("inventory.physical_counts.read", "inventory", "View physical counts"),
    PermissionDefinition("inventory.physical_counts.create", "inventory", "Manage physical counts"),
    PermissionDefinition("purchase.orders.read", "purchase", "View purchase orders"),
    PermissionDefinition("purchase.orders.create", "purchase", "Create purchase orders"),
    PermissionDefinition("purchase.orders.update", "purchase", "Update purchase order drafts"),
    PermissionDefinition("purchase.orders.submit", "purchase", "Submit purchase orders"),
    PermissionDefinition("purchase.orders.approve", "purchase", "Approve purchase orders"),
    PermissionDefinition("purchase.orders.cancel", "purchase", "Cancel purchase orders"),
    PermissionDefinition("purchase.receipts.read", "purchase", "View goods receipts"),
    PermissionDefinition("purchase.receipts.create", "purchase", "Post goods receipts"),
    PermissionDefinition("purchase.direct_purchases.read", "purchase", "View direct purchases"),
    PermissionDefinition("purchase.direct_purchases.create", "purchase", "Post direct purchases"),
    PermissionDefinition("purchase.returns.read", "purchase", "View purchase returns"),
    PermissionDefinition("purchase.returns.create", "purchase", "Post purchase returns"),
    PermissionDefinition("assets.read", "assets", "View assets"),
    PermissionDefinition("assets.create", "assets", "Create assets"),
    PermissionDefinition("assets.update", "assets", "Update and restore assets"),
    PermissionDefinition("assets.delete", "assets", "Delete assets"),
    PermissionDefinition("assets.assign", "assets", "Assign assets to locations"),
    PermissionDefinition("assets.maintain", "assets", "Record asset maintenance"),
    PermissionDefinition("employees.read", "employees", "View employees"),
    PermissionDefinition("employees.create", "employees", "Create employees"),
    PermissionDefinition("employees.update", "employees", "Update and restore employees"),
    PermissionDefinition("employees.delete", "employees", "Delete employees"),
    PermissionDefinition(
        "employees.attendance.read", "employees", "View employee attendance"
    ),
    PermissionDefinition(
        "employees.attendance.create", "employees", "Record employee attendance"
    ),
    PermissionDefinition(
        "employees.attendance.update", "employees", "Update employee attendance"
    ),
)


def seed_initial_admin(
    session: Session,
    username: str = "admin",
    full_name: str = "System Administrator",
) -> SeedResult:
    normalized_username = username.strip()
    normalized_full_name = full_name.strip()
    if not normalized_username or not normalized_full_name:
        raise ValueError("Admin username and full name must not be empty.")

    user = session.scalar(select(User).where(User.username == normalized_username))
    generated_password: Optional[str] = None
    if user is None:
        generated_password = secrets.token_urlsafe(32)
        user = User(
            username=normalized_username,
            full_name=normalized_full_name,
            password_hash=hash_password(generated_password),
            is_active=True,
        )
        session.add(user)
        session.flush()

    role = session.scalar(select(Role).where(Role.name == ADMIN_ROLE_NAME))
    if role is None:
        role = Role(
            name=ADMIN_ROLE_NAME, description="Full access to the seeded permission catalog"
        )
        session.add(role)
        session.flush()

    permission_codes = {item.code for item in ADMIN_PERMISSION_CATALOG}
    permissions = list(
        session.scalars(select(Permission).where(Permission.code.in_(permission_codes)))
    )
    permissions_by_code = {permission.code: permission for permission in permissions}
    for definition in ADMIN_PERMISSION_CATALOG:
        if definition.code not in permissions_by_code:
            permission = Permission(
                code=definition.code,
                module=definition.module,
                description=definition.description,
            )
            session.add(permission)
            permissions.append(permission)
            permissions_by_code[definition.code] = permission

    session.flush()

    assigned_codes = {permission.code for permission in role.permissions}
    role.permissions.extend(
        permission for permission in permissions if permission.code not in assigned_codes
    )
    if role not in user.roles:
        user.roles.append(role)

    return SeedResult(
        username=normalized_username,
        created=generated_password is not None,
        password=generated_password,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the initial Sabuj Pran administrator.")
    parser.add_argument("--username", default="admin", help="Initial administrator username.")
    parser.add_argument(
        "--full-name",
        default="System Administrator",
        help="Initial administrator display name.",
    )
    args = parser.parse_args()

    with SessionLocal.begin() as session:
        result = seed_initial_admin(session, username=args.username, full_name=args.full_name)

    if result.created:
        print("Administrator created.")
        print(f"Username: {result.username}")
        print(f"Temporary password: {result.password}")
        print("Save this password now; it is displayed only once.")
    else:
        print(f"Administrator '{result.username}' already exists; its password was not changed.")


if __name__ == "__main__":
    main()
