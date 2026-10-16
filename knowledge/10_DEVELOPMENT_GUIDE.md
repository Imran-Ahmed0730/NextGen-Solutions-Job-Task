# Sabuj Pran Project Work Documentation

This document explains what has been built in this repository, how the running application is
assembled, what happens in its current user workflows, and how to run and verify the project. It is
implementation documentation, not a second copy of the business-rule list.

## 1. Project at a glance

Sabuj Pran is a web-based ERP-lite for a small manufacturing and trading business. The intended
product brings purchasing, inventory, production, sales, money, party balances, administration,
and reporting into one auditable application.

The repository is a **modular monolith**: one API application and one web application backed by
MySQL. Business areas are separated into Python modules, but they are deployed together. Modules
are not independent services.

The target business cycle is:

```text
Supplier → Purchase → Inventory → Sales order → Production (if needed) → Delivery/Sale → Customer due
          → Collection → Cash/Bank/MFS → Expenses → Management reports
```

The repository is under active phased development. The foundation and authentication/
administration slice are implemented. The complete purchase-to-dashboard ERP cycle is not yet
implemented; see [Section 10](#10-implementation-status).

## 2. Technology and runtime

| Layer | Current implementation |
|---|---|
| Web | Next.js 14 App Router, React 18, TypeScript, Tailwind CSS |
| Form validation | Validate in both frontend (Zod, for immediate UX feedback) and backend (Pydantic, mandatory and authoritative); keep the rules consistent and map API validation errors inline |
| UI components | Accessible StatusSwitch toggle, standardized ActionIcon and IconActionButton controls, searchable Select2-style entity selectors, and a shared required-field marker |
| Notifications | SweetAlert2 toast helper |
| API | FastAPI, Pydantic, SQLAlchemy 2 |
| Database | MySQL 8.4, InnoDB, `utf8mb4` |
| Authentication | JWT access tokens, rotating opaque refresh tokens, Argon2 passwords |
| Migrations | Alembic |
| Runtime/dev orchestration | Docker Compose |
| Backend tests and quality | pytest, Ruff, mypy |
| Frontend tests and quality | Vitest, React Testing Library, TypeScript, Next lint |

The web app runs at `http://localhost:3000`, the API at `http://localhost:8000`, and the default
Compose MySQL service listens on port 3306. API health is exposed at `/health`; the API root `/`
is protected.

## 3. Repository layout

```text
.
├── backend/
│   ├── app/
│   │   ├── api/                 # Health endpoint
│   │   ├── core/                # Configuration, DB, security, exceptions, email
│   │   ├── modules/auth/        # Authentication and user/role administration
│   │   ├── modules/boms/        # BOM master data and material components
│   │   ├── modules/production_orders/ # Production orders, posting, and costing
│   │   ├── modules/inventory/   # Stock ledger, balances, posting service, read APIs
│   │   ├── modules/stock_transfers/ # Atomic inter-warehouse transfers
│   │   ├── modules/units/       # Measurement-unit master-data reference module
│   │   ├── modules/product_categories/ # Hierarchical product categories
│   │   ├── modules/products/    # Products (stocked/trading) with category and unit
│   │   ├── modules/warehouses/  # Storage locations with a single default
│   │   ├── modules/expense_categories/ # Hierarchical expense categories
│   │   ├── modules/income_categories/  # Flat income categories
│   │   ├── modules/payment_methods/    # CASH/BANK/MFS/ONLINE payment methods
│   │   ├── modules/money_accounts/     # Cash/bank/MFS accounts for money movements
│   │   ├── modules/money_transactions/ # Append-only money ledger and balance service
│   │   ├── modules/money_collections/  # Customer collection documents and ledger postings
│   │   ├── modules/supplier_payments/  # Supplier payment documents and bill allocations
│   │   ├── modules/expenses/           # Expense documents (debit money account, credit expense category)
│   │   ├── modules/incomes/            # Income documents (credit money account, income category)
│   │   ├── modules/fund_transfers/     # Inter-account fund transfer documents
│   │   ├── modules/price_lists/        # Price lists and product prices
│   │   ├── modules/company_settings/    # Flexible key/value company settings
│   │   └── main.py              # FastAPI app and router registration
│   ├── alembic/versions/        # Versioned database changes
│   └── tests/                   # Backend service/API/model/mail tests
├── frontend/
│   └── src/
│       ├── app/                 # Routes and page components
│       ├── components/auth/     # Protected shell and user form
│       └── lib/                 # API client, validation, notifications
├── knowledge/                   # Product requirements, schema, flows and plans
├── docker-compose.yml
├── .env.example
└── CLAUDE.md
```

`backend/app/modules/auth/` contains the auth and administration router, Pydantic schemas,
SQLAlchemy models, service logic, repository queries, audit helper, and initial-admin seed script.
`backend/app/modules/units/` is the first Phase 2 business module and follows the same
router/schema/model/service/repository split. `backend/app/modules/product_categories/` follows
that structure for hierarchical categories. The `products`, `warehouses`, `expense_categories`,
`income_categories`, `payment_methods`, `money_accounts`, `price_lists`, and `company_settings` modules follow the same
router/schema/model/service/repository split. `backend/app/core/` contains shared facilities such as
JWT/session validation, configuration, database access, and SMTP delivery.
The Phase 4 `inventory` module provides the append-only stock transaction ledger, product/warehouse
balance projection, the sole stock-posting service, and authenticated stock and ledger read APIs.
The separate `stock_transfers` module uses that posting service to move stock between warehouses
atomically.

The protected app shell uses a permission-filtered, grouped sidebar on desktop and a toggleable
drawer on smaller screens. The top bar shows the current route and signed-in account.

The frontend route tree currently includes:

| Route | Purpose |
|---|---|
| `/login` | Sign in using username, email, or mobile and password |
| `/forgot-password` | Request a reset link using the registered email address |
| `/reset-password` | Set a password using the one-time email link |
| `/` | Protected landing/dashboard foundation |
| `/profile` | View and update the signed-in user's contact details |
| `/change-password` | Change password while signed in |
| `/users` | List, activate, and deactivate user accounts |
| `/users/new` | Create a user and assign roles |
| `/users/[id]` | Edit user details and roles |
| `/roles` | Create/update roles and grant permissions |
| `/permissions` | Read-only permission catalog |
| `/units` | List, create, update, soft-delete, and restore measurement units |
| `/categories` | List, create, update, soft-delete, and restore product categories |
| `/products` | List, create, update, soft-delete, and restore products |
| `/warehouses` | List, create, update, soft-delete, and restore warehouses |
| `/warehouse-stock` | View on-hand, reserved, and available quantities by warehouse |
| `/stock-ledger` | Review product movements with date filters, running balance, and source links |
| `/stock-transfers` | Post inter-warehouse stock transfers and browse transfer history |
| `/stock-adjustments` | Post reasoned stock increases/decreases and browse adjustment history |
| `/expense-categories` | List, create, update, soft-delete, and restore expense categories |
| `/income-categories` | List, create, update, soft-delete, and restore income categories |
| `/payment-methods` | List, create, update, soft-delete, and restore payment methods |
| `/money-accounts` | List, create, update, soft-delete, and restore money accounts |
| `/account-ledger` | Review current account balances and date-filtered money transactions with running balances |
| `/customer-collections` | Post customer collections and view recent collection history |
| `/quotations` | Create, edit, and browse sales quotation drafts |
| `/sales-orders` | Create, edit, browse, view draft sales order details, and post deliveries with COGS |
| `/sales-invoices` | Post invoices from deliveries, apply credit-limit mode, and browse invoice/COGS history |
| `/sales-returns` | Return remaining invoiced quantities, restore stock at original COGS, and reduce customer due |
| `/boms` | Create, edit, browse, soft-delete, and restore Bills of Materials |
| `/production-orders` | Create/edit drafts, start/cancel orders, post actual production, and review costs |
| `/supplier-payments` | Post supplier payments with optional bill allocation and view history |
| `/expenses` | Record operational expenses paid from any money account and browse expense history |
| `/incomes` | Record money received into any account from any income source and browse income history |
| `/fund-transfers` | Move money between accounts and browse transfer history |
| `/price-lists` | List, create, update, soft-delete, and restore price lists and their product prices |
| `/company-settings` | Manage flexible key/value company settings |

Routes are implemented under `frontend/src/app/`. Protected routes use the shared authentication
shell and permission-aware navigation.
Entity selectors with searchable option lists use the shared accessible `SearchableSelect` component
so users can filter products, suppliers, warehouses, categories, units, and documents by their
names/codes. Fixed short enumerations remain native selects. Every required form field must show the
shared red asterisk marker next to its visible label, including required fields in dynamic rows and
table/grid headers. Keep the marker consistent with frontend and backend validation; frontend
validation is for UX and never replaces backend validation.

## 4. Backend request and data flow

An HTTP request follows this general path:

```text
Next.js page
  → frontend apiRequest()
  → FastAPI router
  → Pydantic request schema
  → authentication/permission dependency (when required)
  → auth service
  → SQLAlchemy model/query
  → MySQL
```

The router maps HTTP operations and delegates application behavior to each module's `service.py`.
Pydantic schemas validate incoming payloads and document responses. Services own business
workflows, repositories hold reusable queries, and models map persisted data.
The HTTP interface is REST-style: collection reads/creates use `GET`/`POST`, resource updates use
`PATCH`, and soft deletion uses `DELETE`, with JSON request/response bodies. Category activation is
updated through `PATCH` on the category resource; restoration from soft deletion uses its explicit
restore action.

`backend/app/main.py` registers health, authentication, master-data, sales, and production routers,
configures CORS for `FRONTEND_ORIGIN`, and protects the API root. The auth router is mounted under
`/api/v1/auth`.

## 5. Authentication and account flows

### Sign in and protected requests

1. The login page validates the submitted credentials with Zod and posts them to
   `POST /api/v1/auth/login`.
2. The API verifies the Argon2 password hash. After repeated failures it locks the account for the
   configured duration (current project decision: five failures and 15 minutes).
3. On success, the API creates a persisted refresh session and returns an access token plus
   refresh token.
4. The frontend stores the tokens in the current browser tab's `sessionStorage`.
5. Protected pages request `/api/v1/auth/me`, then display navigation allowed by the profile's
   permissions.
6. If a request receives an expired-session 401, `apiRequest()` rotates the refresh token and
   retries. Concurrent 401 responses share a single refresh operation.

The API validates the access JWT's session ID against an active refresh-session record. Refresh
rotation revokes the old record and creates the next one. Logout revokes the current session.
Password changes/resets and account deactivation revoke sessions as appropriate.

### Password recovery by email

1. The user enters the account's registered email address on `/forgot-password`.
2. `POST /api/v1/auth/forgot-password` looks up an active account by email, case-insensitively.
3. For a matching account, the service invalidates earlier unused reset requests, creates a random
   one-time token, stores only its SHA-256 hash, and sends a link through the configured SMTP
   transport.
4. The link opens `/reset-password?token=...`. The user enters and confirms a new password.
5. `POST /api/v1/auth/reset-password` validates that the token exists, is unused, and has not
   expired. It hashes the new password, marks the token used, clears login lockout, and revokes
   existing sessions.

The API gives the same generic response for existing and unknown email addresses to avoid account
enumeration. It does **not** disclose the reset token in the response, user-management screen, or
audit record. SMTP delivery/configuration failures return an explicit service error. The initial
seeded administrator has no email, so assign the account a valid email from its profile before
using recovery.

For SMTP setup, use the `SMTP_*` keys in `.env`. The host and from-address are required; credentials
are optional only when the relay permits unauthenticated delivery. Port 587 normally uses STARTTLS
(`SMTP_USE_TLS=true`, `SMTP_USE_SSL=false`). Port 465 normally uses implicit SSL
(`SMTP_USE_TLS=false`, `SMTP_USE_SSL=true`). Set the reset-link lifetime with
`PASSWORD_RESET_EXPIRE_MINUTES`; the default is 30 minutes.

### User, role, and permission administration

- Users have unique usernames and optional unique email/mobile values. Administrators can create,
  update, list, activate, and deactivate user records according to their permissions.
- User and role deactivation is soft: it disables access without hard-deleting referenced records.
- Roles receive permissions from the application-owned permission catalog. Users receive access
  through their assigned active roles.
- Protected API operations use permissions named `module.resource.action`. Hiding a UI link is
  only a usability feature; the API independently denies unauthorized requests.
- Mutations write audit records. The audit endpoint is read-only to callers with
  `auth.audit_logs.read`.
- The system prevents removing or deactivating the last administrator access path.

The administrator seed creates the `Administrator` role, initial admin user, and current auth
permission catalog. A newly-created admin password is random and printed once by the seed command;
the seed does not reset an existing account's password.

## 6. Current API surface

The implemented auth API is:

| Method and path | Access/permission | Function |
|---|---|---|
| `POST /api/v1/auth/login` | Public credential flow | Start a session |
| `POST /api/v1/auth/refresh` | Public refresh-token flow | Rotate refresh session |
| `POST /api/v1/auth/logout` | `auth.session.logout` | Revoke current session |
| `POST /api/v1/auth/forgot-password` | Public email flow | Send reset link |
| `POST /api/v1/auth/reset-password` | Public reset-token flow | Consume reset link |
| `GET /api/v1/auth/me` | `auth.profile.read` | Read current profile and permissions |
| `PATCH /api/v1/auth/me` | `auth.profile.update` | Update profile |
| `POST /api/v1/auth/change-password` | `auth.password.change` | Change password |
| `GET /api/v1/auth/users` | `auth.users.read` | List users |
| `POST /api/v1/auth/users` | `auth.users.create` | Create user |
| `GET /api/v1/auth/users/{id}` | `auth.users.read` | Read one user |
| `PATCH /api/v1/auth/users/{id}` | `auth.users.update` | Update user |
| `POST /api/v1/auth/users/{id}/deactivate` | `auth.users.delete` | Deactivate user |
| `POST /api/v1/auth/users/{id}/activate` | `auth.users.update` | Reactivate user |
| `GET /api/v1/auth/roles` | `auth.roles.read` | List roles |
| `POST /api/v1/auth/roles` | `auth.roles.create` | Create role |
| `PATCH /api/v1/auth/roles/{id}` | `auth.roles.update` | Update role and permissions |
| `POST /api/v1/auth/roles/{id}/deactivate` | `auth.roles.delete` | Deactivate role |
| `POST /api/v1/auth/roles/{id}/activate` | `auth.roles.update` | Reactivate role |
| `GET /api/v1/auth/permissions` | `auth.permissions.read` | Read permission catalog |
| `GET /api/v1/auth/audit-logs` | `auth.audit_logs.read` | Read audit records |
| `GET /api/v1/units` | `master_data.units.read` | List active units; `include_inactive=true` includes deleted units |
| `POST /api/v1/units` | `master_data.units.create` | Create a unit |
| `PATCH /api/v1/units/{id}` | `master_data.units.update` | Update a unit |
| `DELETE /api/v1/units/{id}` | `master_data.units.delete` | Soft-delete a unit |
| `POST /api/v1/units/{id}/activate` | `master_data.units.update` | Restore a soft-deleted unit |
| `GET /api/v1/product-categories` | `master_data.product_categories.read` | List categories; `include_inactive=true` includes deleted categories |
| `POST /api/v1/product-categories` | `master_data.product_categories.create` | Create a category with an optional parent and active state |
| `PATCH /api/v1/product-categories/{id}` | `master_data.product_categories.update` | Update a category, parent, or active state |
| `DELETE /api/v1/product-categories/{id}` | `master_data.product_categories.delete` | Soft-delete a category |
| `POST /api/v1/product-categories/{id}/activate` | `master_data.product_categories.update` | Restore a soft-deleted category |
| `GET /api/v1/customers?search=&offset=0&limit=50` | `master_data.customers.read` | Search and page through customers; `include_inactive=true` includes inactive/deleted records |
| `POST /api/v1/customers` / `PATCH /api/v1/customers/{id}` | `master_data.customers.create/update` | Create or update customer details and opening due |
| `GET /api/v1/customers/{id}/statement` | `master_data.customers.read` | Read the current opening-balance statement |
| `GET /api/v1/production/boms` | `production.boms.read` | List active BOMs; `include_inactive=true` includes deleted BOMs |
| `GET /api/v1/production/boms/options` | `production.boms.read` | Read active raw-material and finished-product options |
| `POST /api/v1/production/boms` | `production.boms.create` | Create a BOM with its component lines |
| `PUT /api/v1/production/boms/{id}` | `production.boms.update` | Replace BOM fields and component lines |
| `DELETE /api/v1/production/boms/{id}` | `production.boms.delete` | Soft-delete a BOM |
| `POST /api/v1/production/boms/{id}/activate` | `production.boms.update` | Restore a soft-deleted BOM |
| `GET /api/v1/production/orders/options` | `production.orders.read` | Read active BOM, warehouse, and open Sales Order line choices |
| `GET /api/v1/production/orders` / `GET /api/v1/production/orders/{id}` | `production.orders.read` | List or read production orders with costing snapshots |
| `POST /api/v1/production/orders` / `PUT /api/v1/production/orders/{id}` | `production.orders.create/update` | Create or edit a numbered production-order draft |
| `POST /api/v1/production/orders/{id}/start` | `production.orders.update` | Check material availability and start a draft |
| `POST /api/v1/production/orders/{id}/complete` | `production.orders.update` | Atomically post material consumption, output, and production costs |
| `POST /api/v1/production/orders/{id}/cancel` | `production.orders.update` | Cancel a draft or in-progress order |
| `GET /api/v1/sales/quotations` / `GET /api/v1/sales/quotations/{id}` | `sales.quotations.read` | List or view quotation drafts |
| `GET /api/v1/sales/quotations/options` | `sales.quotations.read` | Read active customers and products for quotation entry |
| `POST /api/v1/sales/quotations` | `sales.quotations.create` | Create a numbered quotation draft and audit snapshot |
| `PUT /api/v1/sales/quotations/{id}` | `sales.quotations.update` | Update a quotation while it remains a draft |
| `POST /api/v1/sales/quotations/{id}/send` | `sales.quotations.update` | Transition a draft quotation to SENT |
| `POST /api/v1/sales/quotations/{id}/accept` / `reject` | `sales.quotations.update` | Record a customer response to a sent quotation |
| `POST /api/v1/sales/quotations/{id}/convert` | `sales.orders.create` | Convert an accepted quotation into one linked Sales Order |
| `GET /api/v1/sales/orders` / `GET /api/v1/sales/orders/{id}` | `sales.orders.read` | List or view sales order drafts and their tracking quantities |
| `GET /api/v1/sales/orders/options` | `sales.orders.read` | Read active customers, warehouses, and products for order entry |
| `POST /api/v1/sales/orders` | `sales.orders.create` | Create a numbered draft sales order and audit snapshot |
| `PUT /api/v1/sales/orders/{id}` | `sales.orders.update` | Update a sales order while it remains a draft |
| `POST /api/v1/sales/orders/{id}/lines/{line_id}/reservations` | `sales.orders.reserve` | Reserve available stock through the Phase 4 inventory service |
| `DELETE /api/v1/sales/orders/{id}/reservations/{reservation_id}` | `sales.orders.reserve` | Release the remaining active reservation quantity |
| `POST /api/v1/sales/orders/{id}/deliveries` | `sales.deliveries.create` | Post delivery through the stock service, consume reservations first, and store unit COGS |
| `GET /api/v1/sales/invoices/options` | `sales.invoices.read` | List posted deliveries that have not yet been invoiced |
| `GET /api/v1/sales/invoices` / `GET /api/v1/sales/invoices/{id}` | `sales.invoices.read` | List or view posted invoices and line snapshots |
| `POST /api/v1/sales/invoices` | `sales.invoices.create` | Post one invoice per delivery, add customer due, and check credit-limit mode |
| `GET /api/v1/sales/returns/options` | `sales.returns.read` | List posted invoices and invoice lines with quantities still returnable |
| `GET /api/v1/sales/returns` / `GET /api/v1/sales/returns/{id}` | `sales.returns.read` | List or view posted sales returns |
| `POST /api/v1/sales/returns` | `sales.returns.create` | Post a return against invoice lines, restore stock at original COGS, and reduce customer due |
| `GET/POST /api/v1/customers/{id}/contacts` | `master_data.customers.read/create` | List or add an additional contact |
| `PATCH/DELETE /api/v1/customers/{id}/contacts/{contact_id}` | `master_data.customers.update/delete` | Update or remove an additional contact |
| `GET /api/v1/suppliers?search=&offset=0&limit=50` | `master_data.suppliers.read` | Search and page through suppliers; `include_inactive=true` includes inactive/deleted records |
| `POST /api/v1/suppliers` / `PATCH /api/v1/suppliers/{id}` | `master_data.suppliers.create/update` | Create or update supplier details and opening due |
| `GET /api/v1/suppliers/{id}/statement` | `master_data.suppliers.read` | Read the current opening-balance statement |
| `GET/POST /api/v1/suppliers/{id}/contacts` | `master_data.suppliers.read/create` | List or add an additional contact |
| `PATCH/DELETE /api/v1/suppliers/{id}/contacts/{contact_id}` | `master_data.suppliers.update/delete` | Update or remove an additional contact |
| `GET /api/v1/products` | `master_data.products.read` | List active products; `include_inactive=true` includes deleted products |
| `POST /api/v1/products` | `master_data.products.create` | Create a product with SKU, type, category, unit, and pricing |
| `PATCH /api/v1/products/{id}` | `master_data.products.update` | Update a product |
| `DELETE /api/v1/products/{id}` | `master_data.products.delete` | Soft-delete a product |
| `POST /api/v1/products/{id}/activate` | `master_data.products.update` | Restore a soft-deleted product |
| `GET /api/v1/warehouses` | `master_data.warehouses.read` | List active warehouses; `include_inactive=true` includes deleted warehouses |
| `POST /api/v1/warehouses` | `master_data.warehouses.create` | Create a warehouse, optionally as the single default |
| `PATCH /api/v1/warehouses/{id}` | `master_data.warehouses.update` | Update a warehouse |
| `DELETE /api/v1/warehouses/{id}` | `master_data.warehouses.delete` | Soft-delete a warehouse |
| `POST /api/v1/warehouses/{id}/activate` | `master_data.warehouses.update` | Restore a soft-deleted warehouse |
| `GET /api/v1/inventory/transfers/options` | `inventory.transfers.read` | Read transfer warehouse and stocked-product choices |
| `GET /api/v1/inventory/transfers?offset=0&limit=50` | `inventory.transfers.read` | List posted stock transfers |
| `GET /api/v1/inventory/transfers/{id}` | `inventory.transfers.read` | Read one posted stock transfer |
| `POST /api/v1/inventory/transfers` | `inventory.transfers.create` | Atomically post a transfer and paired stock-ledger movements |
| `GET /api/v1/inventory/ledger/options` | `inventory.stock.read` | Read stocked-product and warehouse filter options |
| `GET /api/v1/inventory/ledger?product_id=&warehouse_id=&date_from=&date_to=&offset=0&limit=100` | `inventory.stock.read` | Read paginated product movements with running on-hand balance; running balances include movements before `date_from` |
| `GET /api/v1/inventory/adjustments/options` | `inventory.adjustments.read` | Read adjustment warehouse and stocked-product choices |
| `GET /api/v1/inventory/adjustments?offset=0&limit=50` | `inventory.adjustments.read` | List posted stock adjustments |
| `GET /api/v1/inventory/adjustments/{id}` | `inventory.adjustments.read` | Read one posted stock adjustment |
| `POST /api/v1/inventory/adjustments` | `inventory.adjustments.create` | Atomically post signed adjustment lines and stock-ledger movements |
| `GET /api/v1/expense-categories` | `master_data.expense_categories.read` | List expense categories; `include_inactive=true` includes deleted categories |
| `POST /api/v1/expense-categories` | `master_data.expense_categories.create` | Create an expense category with an optional parent |
| `PATCH /api/v1/expense-categories/{id}` | `master_data.expense_categories.update` | Update an expense category |
| `DELETE /api/v1/expense-categories/{id}` | `master_data.expense_categories.delete` | Soft-delete an expense category |
| `POST /api/v1/expense-categories/{id}/activate` | `master_data.expense_categories.update` | Restore a soft-deleted expense category |
| `GET /api/v1/income-categories` | `master_data.income_categories.read` | List income categories; `include_inactive=true` includes deleted categories |
| `POST /api/v1/income-categories` | `master_data.income_categories.create` | Create an income category |
| `PATCH /api/v1/income-categories/{id}` | `master_data.income_categories.update` | Update an income category |
| `DELETE /api/v1/income-categories/{id}` | `master_data.income_categories.delete` | Soft-delete an income category |
| `POST /api/v1/income-categories/{id}/activate` | `master_data.income_categories.update` | Restore a soft-deleted income category |
| `GET /api/v1/payment-methods` | `master_data.payment_methods.read` | List active payment methods; `include_inactive=true` includes deleted methods |
| `POST /api/v1/payment-methods` | `master_data.payment_methods.create` | Create a payment method (CASH/BANK/MFS/ONLINE) |
| `PATCH /api/v1/payment-methods/{id}` | `master_data.payment_methods.update` | Update a payment method |
| `DELETE /api/v1/payment-methods/{id}` | `master_data.payment_methods.delete` | Soft-delete a payment method |
| `POST /api/v1/payment-methods/{id}/activate` | `master_data.payment_methods.update` | Restore a soft-deleted payment method |
| `GET /api/v1/money-accounts` | `master_data.money_accounts.read` | List active money accounts; `include_inactive=true` includes deleted accounts |
| `POST /api/v1/money-accounts` | `master_data.money_accounts.create` | Create a money account with opening balance and overdraft flag |
| `PATCH /api/v1/money-accounts/{id}` | `master_data.money_accounts.update` | Update a money account |
| `DELETE /api/v1/money-accounts/{id}` | `master_data.money_accounts.delete` | Soft-delete a money account |
| `POST /api/v1/money-accounts/{id}/activate` | `master_data.money_accounts.update` | Restore a soft-deleted money account |
| `GET /api/v1/money-transactions/accounts` | `money.transactions.read` | List active money accounts with opening and current balances |
| `GET /api/v1/money-transactions/accounts/{id}/balance` | `money.transactions.read` | Read opening balance plus posted money transactions |
| `GET /api/v1/price-lists` | `master_data.price_lists.read` | List price lists; `include_inactive=true` includes deleted lists |
| `POST /api/v1/price-lists` | `master_data.price_lists.create` | Create a price list with optional validity range and default flag |
| `PATCH /api/v1/price-lists/{id}` | `master_data.price_lists.update` | Update a price list |
| `DELETE /api/v1/price-lists/{id}` | `master_data.price_lists.delete` | Soft-delete a price list |
| `POST /api/v1/price-lists/{id}/activate` | `master_data.price_lists.update` | Restore a soft-deleted price list |
| `GET /api/v1/price-lists/{id}/prices` | `master_data.price_lists.read` | List product prices for a price list |
| `POST /api/v1/price-lists/{id}/prices` | `master_data.price_lists.create` | Add a product price to a price list |
| `PATCH /api/v1/price-lists/{id}/prices/{price_id}` | `master_data.price_lists.update` | Update a product price |
| `DELETE /api/v1/price-lists/{id}/prices/{price_id}` | `master_data.price_lists.delete` | Remove a product price |
| `GET /api/v1/company-settings` | `master_data.company_settings.read` | List company settings |
| `GET /api/v1/company-settings/branding` | `auth.profile.read` | Read authenticated workspace brand defaults and saved assets |
| `PUT /api/v1/company-settings/assets/{logo|favicon}` | `master_data.company_settings.update` | Upload validated company brand image |
| `POST /api/v1/company-settings` | `master_data.company_settings.create` | Create a company setting |
| `GET /api/v1/company-settings/{key}` | `master_data.company_settings.read` | Read a company setting |
| `PATCH /api/v1/company-settings/{key}` | `master_data.company_settings.update` | Update a company setting |
| `DELETE /api/v1/company-settings/{key}` | `master_data.company_settings.delete` | Delete a company setting |

The public health endpoint is `GET /health`. The API root endpoint requires
`auth.profile.read`. Query pagination for user/audit/unit lists currently uses `offset` and
`limit`.

## 7. Database and migrations

Authentication currently persists:

- `users`: login identity, profile, password hash, active state, login-failure count and lock time.
- `roles` and `permissions`: named roles and the permission catalog.
- `user_roles` and `role_permissions`: many-to-many grants.
- `refresh_tokens`: hashed refresh token and session expiry/revocation state.
- `password_resets`: hashed one-time reset token, expiry, and used state.
- `audit_logs`: append-only event details and optional actor.

The first master-data migration adds `units` with its name, unique code, fractional-quantity flag,
active/deleted state, and timestamps. Unit changes are recorded in `audit_logs`; deleted units
remain stored and may be restored. The next migration adds `product_categories`, with an optional
self-referencing parent, active/deleted state, and timestamps. Category services reject missing or
inactive parents and parent changes that would create a cycle. Category create/update/delete/restore
operations write audit records. Active state can be switched with the screen's accessible
`StatusSwitch` toggle control; deactivation hides a category from the default list without marking it
deleted. Deleting a category is a separate soft-delete action and preserves child references.

The subsequent master-data migrations add `products` (stocked/trading/finished, with category and
unit references, reorder level, default sales price, and soft-delete state), `warehouses` (storage
locations where at most one row holds the default flag), hierarchical `expense_categories`, flat
`income_categories`, `payment_methods` (typed CASH/BANK/MFS/ONLINE), and `money_accounts` (typed
CASH/BANK/MFS with an optional payment-method reference, optional account number, `opening_balance`
as `DECIMAL(18,2)`, and an `allow_overdraft` flag). Each module validates its inputs, writes audit
records on create/update/status/delete/restore, and uses soft delete for removal. Money-account
creation rejects a missing or deleted payment method.

The subsequent master-data migration adds `price_lists` (named price lists with an `is_default`
flag and optional validity range) and `product_prices` (one price per product per price list). A
price list may be soft-deleted; suspended/referenced product records cannot be hard-deleted.
Product prices validate product and price-list references and prevent duplicates.

Company settings are implemented as a flexible key/value store. Document numbering is implemented
as typed sequences with locking, gap-free number generation.

The current migration chain is:

1. `20261012_initial_empty` — initial empty migration.
2. `20261013_auth_models` — core auth/role/permission/session/reset tables.
3. `20261013_auth_audit` — role active flag and audit table.
4. `20261013_remove_reset_perm` — removes the obsolete operator-issued reset
   permission now that recovery is email-based.
5. `20261013_units` — creates the first master-data table.
6. `20261013_categories` — creates hierarchical product categories.
7. `20261013_products` — creates the products table.
8. `20261013_warehouses` — creates the warehouses table.
9. `20261013_expense_categories` — creates hierarchical expense categories.
10. `20261013_income_categories` — creates flat income categories.
11. `20261013_payment_methods` — creates typed payment methods.
12. `20261013_money_accounts` — creates money accounts with an optional payment-method reference.
13. `20261013_price_lists` — creates price lists and product prices.
14. `20261013_company_settings` — creates the key/value company settings table.
15. `20261013_document_sequences` — creates document numbering sequences.

Do not edit a migration after it has been applied to an environment. Add a new Alembic revision for
subsequent schema changes. Offline SQL generation checks migration construction; applying a
migration to the configured database should be an intentional deployment operation.

## 8. Running the project

### Docker Compose

1. Copy `.env.example` to `.env`.
2. Set a private `SECRET_KEY`, database connection values, and SMTP values if password recovery is
   needed.
3. Start services:

   ```powershell
   docker compose up --build
   ```

4. Apply migrations:

   ```powershell
   docker compose run --build --rm --no-deps api alembic upgrade head
   ```

5. Create the initial admin if needed:

   ```powershell
   docker compose run --rm --no-deps api python -m app.modules.auth.seed
   ```

6. Seed company defaults from the environment if needed:

   ```powershell
   docker compose run --rm --no-deps api python -m app.modules.company_settings.seed
   ```

   Existing values are preserved; use `--overwrite` only when intentionally replacing them.

7. Open `http://localhost:3000/login`. API health is at `http://localhost:8000/health`.

Compose has `db`, `api`, and `web` services. The development web service runs `next dev`; the API
uses Uvicorn reload. The local MySQL data persists in the Compose-managed `mysql_data` volume.

### Local frontend

Run the API and database first, then:

```powershell
Set-Location frontend
npm install
npm run dev
```

The browser-facing API URL is controlled by `NEXT_PUBLIC_API_URL`. Configure `FRONTEND_ORIGIN` to
match the browser origin so the API's CORS policy permits requests.

## 9. Checks and tests

Run backend checks from `backend/` using the selected virtual environment:

```powershell
python -m pytest -q
python -m ruff check app tests
python -m mypy app
python -m alembic upgrade head --sql
```

Run frontend checks from `frontend/`:

```powershell
npm run typecheck
npm run test
npm run lint
npm run build
```

Tests use an isolated in-memory SQLite database for auth API behavior; migration SQL generation
uses the configured Alembic URL in offline mode. Neither operation applies schema changes to the
live MySQL database.

The Phase 1 checks previously run for this project passed: backend suite (34 tests), Ruff, mypy,
frontend typecheck/tests/lint/build, and offline migration generation. Subsequent notification and
email-reset UI adjustments also passed frontend typecheck, tests, lint, and production build.

## 10. Implementation status

### Implemented foundation

- Monorepo, Docker Compose services, environment configuration, API health endpoint, frontend
  foundation, migration framework, lint/type/test tooling, and CI.

### Implemented Phase 1 — Authentication and administration

- User, role, permission, refresh-session, password-reset, and audit models.
- Login/logout/refresh, revocable JWT sessions, Argon2 passwords, lockout, and granular permission
  dependencies.
- Email-based password recovery with configurable SMTP and one-time hashed reset tokens.
- Profile update and password change.
- User and role administration, permission catalog, audit API, administrator seeding.
- Login, forgot/reset password, protected shell, profile, change-password, users, roles, and
  permissions screens.
- SweetAlert2 toast feedback for frontend validation, success, and action errors.

### Implemented Phase 2 slices — Master data

- Unit API, persistence model, schema validation, repository, and service.
- Permission-controlled unit list/create/update/delete/restore, with audit entries and soft-delete
  behavior.
- Administrator seed includes the `master_data.units.*` permissions.
- Units screen is available at `/units`.
- Product-category API and persistence model with optional self-referencing parent categories.
- Parent existence/active-state validation and cycle prevention for category hierarchy changes.
- Permission-controlled category list/create/update/delete/restore, with audit entries and
  soft-delete behavior.
- Administrator seed includes the `master_data.product_categories.*` permissions.
- Product-category screen is available at `/categories`.
- Products with SKU/type/category/unit, reorder level, default sales price, stocked flag, and
  soft-delete, exposed at `/products`.
- Warehouses with a single enforced default, exposed at `/warehouses`.
- Hierarchical expense categories at `/expense-categories` and flat income categories at
  `/income-categories`.
- Payment methods (CASH/BANK/MFS/ONLINE) at `/payment-methods`.
- Money accounts (CASH/BANK/MFS) with optional payment-method link, account number, opening
  balance, and overdraft flag at `/money-accounts`.
- Price lists with default handling and validity dates at `/price-lists`, plus product-price
  management for each list.
- Company settings as a flexible key/value store at `/company-settings`, with an environment-aware
  seeder. Initial defaults include company profile, logo/favicon brand assets, currency, timezone,
  invoice footer, credit-limit mode, and receiving tolerance. Uploaded logo/favicon files are
  validated, stored under `MEDIA_ROOT`, and persisted by the Compose `backend/media` mount. The
  seeder preserves configured values unless run with `--overwrite`; invoice rendering and
  transaction effects belong to the later sales/purchase phases.
- Document numbering sequences at `/document-numbering`, with locking gap-free number generation.
- Each module validates inputs, writes audit records, uses soft delete, and ships
  permission-controlled list/create/update/delete/restore endpoints.

### Implemented Phase 3 — Customers and suppliers

- Customer and supplier CRUD APIs with primary contact information, opening dues, status, audit,
  soft delete/restore, and granular permissions.
- Additional party contacts have API and UI create/read/update/delete flows.
- Party lists support server-side search by code, name, mobile, or email, plus offset/limit paging.
- Party contact data is validated on both frontend and backend, including email syntax and the
  11-digit Bangladesh local mobile format.
- Customer and supplier statements show the opening-balance entry and running opening balance.
  Posted sales/purchase documents, returns, collections, and payments are not yet implemented;
  statement integration with those transactions is deferred to their respective phases.
- Focused API tests cover validation, statement opening entries, search, and permission denials for
  statement and contact routes.

### Phase 4 in progress — Inventory ledger and warehouse stock

- Alembic creates `stock_transactions` and composite-key `stock_balances` with product, warehouse,
  and actor references, quantity precision, and ledger query indexes.
- `post_stock_movement()` is the only stock-balance writer. It locks the product row, validates
  movement direction and unit precision, prevents stocked products from going below zero or below
  reserved stock, appends the signed ledger row, updates the balance, and records the audit event
  without committing so the caller can include it in a larger transaction.
- Authenticated `GET /api/v1/inventory/stock` and `GET /api/v1/inventory/ledger` routes use the
  `inventory.stock.read` permission. The administrator seed catalog includes this permission.
- Authenticated `GET /api/v1/inventory/warehouse-stock` returns named product/warehouse rows,
  including zero balances for active stocked products, with warehouse and product search filters
  and pagination. The `/warehouse-stock` screen displays on-hand, reserved, and available amounts
  and is permission-gated in the navigation.
- The `stock_transfers` module posts a transfer document and paired `TRANSFER_OUT`/`TRANSFER_IN`
  ledger entries for each line in a single database transaction. Any posting failure rolls back the
  document, sequence increment, audit entries, ledger rows, and balances together. Configure a
  `STOCK_TRANSFER` sequence in Document Numbering before posting transfers. The `/stock-transfers`
  screen supports multiple products and displays paginated posted-transfer history; access uses
  `inventory.transfers.read` and `inventory.transfers.create`.
- The `stock_adjustments` module posts a reasoned document with positive or negative quantity lines
  as `ADJUSTMENT_IN` or `ADJUSTMENT_OUT`. It captures current product average cost on each line,
  routes every stock change through the shared posting service, and rolls back the document,
  sequence, audits, ledger, and balances together on failure. Configure a `STOCK_ADJUSTMENT`
  sequence before posting. The `/stock-adjustments` screen supports multiple lines and paginated
  history; access uses `inventory.adjustments.read` and `inventory.adjustments.create`. Approval
  hooks remain part of the later Approvals phase.
- A weighted-average-cost helper follows the PRD formula; transaction-specific costing integration
  remains for purchase and production posting workflows.
- The inventory reservation service supports reserve, partial release, and partial consume. Reserve
  changes `qty_reserved` only; consume reduces the reserved amount, increments the order line's
  `qty_delivered`, and posts a `SALE_DELIVERY` movement through the shared stock service in the
  caller's transaction. A minimal sales-order and sales-order-line persistence foundation supplies
  the reservation FK, but Sales workflows,
  quotation linkage, and status transitions are not implemented yet.
- Physical counts snapshot all active stocked products for a warehouse, accept partial quantity
  entry, calculate variances against the snapshot, and post signed `COUNT_ADJUSTMENT` movements
  atomically. Posting refuses stale stock or a changed stocked-product scope. The count number is
  allocated only when posted, so abandoned open sheets do not consume posted document numbers.
- Inventory invariant tests assert that the balance equals the signed ledger total across every
  movement type and that a stocked product cannot issue reserved stock or become negative. A real
  concurrent-posting test is opt-in: set `INVENTORY_CONCURRENCY_DATABASE_URL` to a separately
  migrated MySQL database whose name ends in `_test`, then run
  `pytest tests/test_inventory_concurrency.py`. The test refuses non-MySQL URLs and databases
  without the `_test` suffix, uses uniquely named records, and removes only those records afterward;
  it never falls back to the application or shared development database. On 2026-10-15 this test
  passed against `sabuj_pran_test` on MySQL 8.4 in a disposable Docker container after upgrading it
  to the current Alembic head. The container was removed after the run; no test database volume was
  retained.
- Reservation operations are service-level only until Phase 7 Sales endpoints integrate them with
  order lifecycle rules.

### Phase 5 in progress — Purchase Order drafts

- The `purchase_orders` and `purchase_order_lines` tables store the purchase-order header, stocked
  product lines, totals, and received quantities. Their migration also introduces read, create, and
  draft-update permissions for the Administrator role.
- `POST /api/v1/purchase/orders` creates a DRAFT; `PUT /api/v1/purchase/orders/{id}` edits DRAFT
  documents only. Both validate active suppliers/warehouses and active stocked products, preserve
  decimal quantities and money as `Decimal`, calculate line totals to cents, use the central
  `PURCHASE_ORDER` document sequence, and write audit snapshots in the same transaction.
- `GET /api/v1/purchase/orders` lists documents, `GET /api/v1/purchase/orders/{id}` retrieves one,
  and `GET /api/v1/purchase/orders/options` supplies active suppliers, warehouses, and stocked
  products. The `/purchase-orders` screen supports draft creation/editing and list/details, gated by
  `purchase.orders.read`, `purchase.orders.create`, and `purchase.orders.update`.
- The UI/API currently implement draft workflows only. Submit/approve/reject transitions are
  deferred to Phase 11. Configure a `PURCHASE_ORDER` sequence before creating drafts.

### Phase 5 in progress — Goods Receipts

- Goods Receipt documents can be posted only against an `APPROVED` or `PARTIALLY_RECEIVED` purchase
  order. Purchase-order submission and approval are deferred to Phase 11, so this screen will have
  no eligible orders until an order is approved.
- Posting validates each receipt line against its PO line and the configured
  `receipt_tolerance_pct`, then atomically records the immutable receipt, `PURCHASE_RECEIPT` stock
  ledger entries and balances, weighted-average product costs, PO received quantities/status, and
  audit records. The `GOODS_RECEIPT` sequence must be configured before posting.
- Supplier statements include posted Goods Receipts and Direct Purchases in the running due
  balance. Posted Purchase Returns and Supplier Payments are included as negative due entries.
- The `/goods-receipts` screen supports choosing an eligible PO, entering received quantities and
  unit costs, posting, and viewing paginated receipt history. Access is gated by
  `purchase.receipts.read` and `purchase.receipts.create`.

### Phase 5 in progress — Direct Purchases

- A Direct Purchase posts without a purchase order. It validates an active supplier, warehouse, and
  stocked products, then atomically records the immutable purchase, `PURCHASE_RECEIPT` stock ledger
  entries and balances, weighted-average product costs, and audit records.
- Direct Purchases are credit-only in this phase: `paid_amount` is zero and no money account is
  recorded. Supplier statements include both posted Goods Receipts and Direct Purchases; purchase
  returns and supplier payments are handled by their respective modules.
- Configure the `DIRECT_PURCHASE` sequence before posting. The `/direct-purchases` screen is gated
  by `purchase.direct_purchases.read` and `purchase.direct_purchases.create`.

### Phase 5 in progress — Purchase Returns

- A Purchase Return is posted against an original Goods Receipt and its lines. Returned quantities
  cannot exceed the received quantity less prior returns; each return line takes the original
  receipt unit cost rather than the product's current average cost.
- Posting locks the source receipt and lines, then atomically writes `PURCHASE_RETURN` stock
  movements, reduces supplier due, records the immutable return and audit entry, and advances the
  `PURCHASE_RETURN` document sequence. Insufficient stock or any other posting failure rolls back
  all effects. Returns against Direct Purchases are not in the current schema.
- Supplier statements include posted returns as negative due entries. The `/purchase-returns`
  screen provides eligible Goods Receipt lines, quantity validation, posting, and paginated history;
  access is gated by `purchase.returns.read` and `purchase.returns.create`.

### Phase 6 — Money ledger, customer collections, supplier payments, expenses, incomes, and fund transfers

- The `money_transactions` table is an append-only signed ledger with transaction type, account,
  source, party, date, and audit fields. The balance service calculates each account as
  `money_accounts.opening_balance + SUM(money_transactions.amount_signed)`.
- Posting locks the account row and reads ledger rows with locking/current-read semantics before
  checking the resulting balance, preventing concurrent postings or an older transaction snapshot
  from spending the same funds on MySQL. Negative resulting balances are rejected unless that
  account permits overdrafts. Each transaction and its audit entry are written in the caller's
  database transaction; the service does not commit independently.
- The account's `opening_balance` is the pre-ledger baseline. `OPENING` entries represent later
  signed adjustments, and account maintenance rejects changing the baseline after the first ledger
  transaction. Customer Collections and Supplier Payments call the shared service so their
  documents, signed money-ledger entries, and audit rows post atomically. Collections reduce the
  customer statement due and increase the chosen account; payments reduce supplier due and the
  chosen account. Supplier payments can be allocated to outstanding Goods Receipts or Direct
  Purchases; customer collections remain party-level until invoices are implemented in Phase 7.
  Both screens use permission-gated searchable party/account selectors. The balance read endpoint
  is gated by `money.transactions.read`; arbitrary transaction posting is intentionally available
  only through the service so document workflows can post the money effect atomically. Configure
  the `CUSTOMER_COLLECTION` and `SUPPLIER_PAYMENT` document sequences before posting.
- **Expenses** — `POST /api/v1/expenses` records a debit against a money account and associates
  the spend with an expense category. The `EXPENSE` document sequence must be configured before
  posting. Permissions: `money.expenses.read`, `money.expenses.create`. Frontend: `/expenses`.
- **Incomes** — `POST /api/v1/incomes` records a credit to a money account for a given income
  category. The `INCOME` document sequence must be configured before posting. Permissions:
  `money.incomes.read`, `money.incomes.create`. Frontend: `/incomes`.
- **Fund Transfers** — `POST /api/v1/fund-transfers` moves an amount from one money account to
  another atomically (one debit + one credit transaction). Rejects same-account transfers and
  enforces the overdraft guard on the source account. The `FUND_TRANSFER` document sequence must
  be configured before posting. Permissions: `money.transfers.read`, `money.transfers.create`.
  Frontend: `/fund-transfers`.
- **Bills of Materials** — A BOM defines a stocked FINISHED product, output quantity, and one or
  more unique stocked RAW material lines. The service validates product types, active state,
  stockability, and whole-quantity units; quantities use three decimals and default labor/overhead
  use two. Create, full replacement, soft-delete, and restore operations are audited. Permissions:
  `production.boms.read`, `production.boms.create`, `production.boms.update`, and
  `production.boms.delete` (assigned to Administrator). Frontend: `/boms`.
- **Production Orders** — Drafts are numbered centrally and reference an active BOM, planned
  quantity, and warehouse; they may optionally link to a matching Sales Order line. Start checks
  availability of the scaled raw-material quantities.
  Completion locks the finished and raw products in ID order, snapshots material quantities and
  average costs, computes material + labor + overhead cost, then posts `PRODUCTION_CONSUME` and
  `PRODUCTION_OUTPUT` through the inventory service in one transaction. The finished-good average
  cost is updated using the production unit cost; when linked, the Sales Order line's `qty_produced`
  and audit snapshot are updated in that same transaction. Linked output cannot exceed the line's
  unreserved, undelivered remaining quantity. Each production order stores consumption/output and
  total cost snapshots. Audit records cover create, edit, start, cancel, and completion. Permissions:
  `production.orders.read`, `production.orders.create`, and `production.orders.update` (assigned to
  Administrator). Configure the `PRODUCTION_ORDER` document sequence. Frontend:
  `/production-orders`.
- **Quotations** — Quotations are created with status `DRAFT`; the service validates active
  customers and products, calculates line totals and subtotal using decimal arithmetic, checks that
  the discount does not exceed subtotal, allocates the central `QUOTATION` number, and writes audit
  snapshots in the same transaction. Only DRAFT quotations can be edited. Transitions are
  `DRAFT → SENT → ACCEPTED` or `REJECTED`; invalid transitions return a conflict. Conversion is
  allowed only from ACCEPTED, copies customer, lines, prices, discount, and note into a draft Sales
  Order, and asks for order date and warehouse. The locked quotation row and unique
  `sales_orders.quotation_id` enforce one-time conversion transactionally. Permissions:
  `sales.quotations.read`, `sales.quotations.create`, and `sales.quotations.update`. Frontend:
  `/quotations`.
- **Sales Orders** — Orders are created with status `DRAFT`; the service validates active customer,
  warehouse, and products, calculates line totals and discount using decimal arithmetic, allocates
  the central `SALES_ORDER` number, and writes audit snapshots transactionally. Users explicitly
  reserve and release stock through the Phase 4 inventory reservation service using
  `sales.orders.reserve`. Reservation history is shown per line; edits are rejected once any
  reservation history exists, even after release. Draft creation itself does not reserve stock.
  Delivery posting consumes reservations first, reserves and immediately consumes any additional
  available quantity in the same transaction, and stores the stock transaction's unit cost on each
  delivery line. Partial delivery leaves the Sales Order status unchanged; order details show
  Ordered, Available stock (on-hand minus reserved), Reserved, Produced, Delivered, and Remaining
  (ordered minus delivered) quantities along with delivery/COGS history. Permission:
  `sales.deliveries.create` (included in the Administrator role). Permissions:
  `sales.orders.read`, `sales.orders.create`, `sales.orders.update`,
  `sales.orders.reserve`, and `sales.deliveries.create`. Frontend: `/sales-orders`.
- **Sales Invoices** — An invoice is posted from one posted delivery and cannot be edited or posted
  twice. Its lines snapshot the linked order's unit price and the delivery's stored COGS. Header
  totals include the proportionate Sales Order discount and COGS. Customer statements include
  posted invoice totals; the current due plus the invoice total is compared with the customer's
  credit limit. `credit_limit_mode=BLOCK` rejects an over-limit invoice; `WARN` posts it and returns a
  visible warning. Configure an `INVOICE` document-number sequence before posting. Permissions:
  `sales.invoices.read` and `sales.invoices.create` (both included in the Administrator role).
  Frontend: `/sales-invoices`.
- **Sales Returns** — Returns reference a posted invoice and its lines; quantities cannot exceed
  each line's remaining invoiced quantity. The return's stock is posted through the inventory
  service at stored invoice-line COGS. Refund values use the invoice's discount-adjusted line value
  (with any rounding remainder applied to the final quantity returned), and posted return totals
  reduce customer due. The customer and invoice are locked during posting to serialize due and
  return-quantity checks. Configure a `SALES_RETURN` document-number sequence before posting.
  Permissions: `sales.returns.read` and `sales.returns.create` (both included in the Administrator
  role). Frontend: `/sales-returns`.
- **Account Ledger** — `GET /api/v1/money-transactions/accounts/{id}/ledger` returns a date-filtered
  list of transactions for a given account with a running balance per row and an opening-period balance
  calculated from all prior transactions. The `/account-ledger` screen lists current balances and
  provides a date-filtered cash-book view. Gated by `money.transactions.read`.
- **Purchase Order lifecycle** — Purchase Orders now support `POST /{id}/submit` (DRAFT →
  PENDING_APPROVAL, requires `purchase.orders.submit`), `POST /{id}/approve`
  (PENDING_APPROVAL or DRAFT → APPROVED, requires `purchase.orders.approve`), and
  `POST /{id}/cancel` (DRAFT or PENDING_APPROVAL → CANCELLED, requires `purchase.orders.cancel`;
  blocked if any quantity has been received). The frontend `/purchase-orders` screen exposes these
  actions based on the caller's permissions and the order's current status.

### Planned, not yet implemented

The remaining roadmap includes the rest of Sales, production, assets, employees,
approvals, reports/dashboard, and full-cycle hardening. Consult
`06_TODO.md` for the current checklist and `05_PLAN.md` for ordering and exit criteria. Do not claim
these workflows work end-to-end until their modules, persistence, permissions, tests, and screens
are actually delivered.

## 11. Project documentation map

| File | What it documents |
|---|---|
| `01_PROJECT.md` | Product purpose, goals, boundaries, and module list |
| `02_TECH_STACK.md` | Fixed stack and architecture conventions |
| `03_PRD.md` | Product features and acceptance criteria |
| `04_RULES.md` | Binding business, engineering, and AI rules |
| `05_PLAN.md` | Phase dependencies and exit criteria |
| `06_TODO.md` | Delivered work, open questions, and decisions |
| `07_DESIGN.md` | UI/UX patterns and visual behavior |
| `08_APP_FLOW.md` | Navigation and process flows |
| `09_SCHEMA.md` | Planned database model |
| `Project_Requirement.md` | Clean technical implementation blueprint and phase/screen overview |
| `10_DEVELOPMENT_GUIDE.md` | This repository's architecture, current features, operations, and implementation status |
| `CLAUDE.md` | Concise agent context that points to the source documents |
