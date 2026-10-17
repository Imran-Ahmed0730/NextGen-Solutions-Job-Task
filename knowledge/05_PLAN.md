# DEVELOPMENT PLAN

Timeline is ignored; phases are ordered by dependency. A phase is complete only when its **Exit criteria** pass (see Rule E-15).

## Dependency order
```
0 Foundation → 1 Auth → 2 Master Data → 3 Parties → 4 Inventory Engine
→ 5 Purchase → 6 Money → 7 Sales → 8 Production → 9 Assets → 10 Employees
→ 11 Approvals → 12 Reports & Dashboard → 13 Hardening
```
Inventory (4) comes before Purchase, Sales and Production. Money (6) comes before Sales so
collections and dues can be tested. Sales orders and reservations (7) provide the source for
production-order links and shortage fulfillment in Production (8). Approvals (11) are built as a
generic engine; earlier phases leave hook points (`requires_approval` flag, status
`PENDING_APPROVAL`).

The AI software-development practice roadmap explicitly numbers phases through Phase 7 (Sales) but
does not assign Production a phase. Production remains required by `03_PRD.md` and `09_SCHEMA.md`;
Phase 8 below is this project's supplemental implementation phase for that required scope.

---
## Phase 0 — Foundation
**Build:** monorepo, backend skeleton, frontend skeleton, Docker compose (api, web, db), env config, Alembic, pytest + Vitest, lint/format/mypy, CI, `CLAUDE.md`, error handling, base response format, DB session/transaction helper, health endpoint.
**Exit:** `docker compose up` shows web + api health; CI green; one sample test passes in each stack.

## Phase 1 — Authentication & Security
**Build:** users, roles, permissions, role_permissions, login (JWT access/refresh), forgot/reset/change password, profile, permission dependency, permission-aware nav, audit service foundation, seed admin.
**Screens:** Login, Forgot Password, My Profile, Change Password, User List, User Add/Edit, Roles, Permissions.
**Exit:** a user without permission gets 403 on every protected endpoint (tests); audit rows written for user changes. **Do not proceed until access control works.**

## Phase 2 — Master Data & Setup
**Build:** units (template module), categories, products, price lists, warehouses, expense/income categories, payment methods, money accounts, company settings, document numbering service.
**Screens:** Product List (+add/edit), Categories, Units, Price List, Expense Categories, Income Categories, Payment Methods, Warehouses, Money Accounts, Company Settings, Document Numbering.
**Exit:** CRUD + validation + soft delete + permissions + audit; numbering gap-free in tests.

**Progress:** The Phase 2 modules currently present in the repository are implemented: units,
categories, products, price lists, warehouses, expense/income categories, payment methods, money
accounts, company settings, and document numbering. Their APIs, screens, permissions, validation,
audit behavior, and focused tests are documented in `10_DEVELOPMENT_GUIDE.md`. Re-run the relevant
suite before release; this status is based on the current implementation inventory.

## Phase 3 — Customers & Suppliers
**Build:** customer/supplier masters, additional contacts, opening dues, and statements.
**Screens:** Customer List/Add/Edit, Customer Contacts, Customer Statement, Supplier List/Add/Edit,
Supplier Contacts, Supplier Statement.
**Phase 3 exit:** customer/supplier CRUD and contact CRUD work with permissions, validation, soft
delete/restore, and audit; the statement shows an opening-balance entry and its running balance.
Sales/purchase/collection/payment statement entries are explicitly deferred until Phases 5, 6, and
7 provide those posted transaction sources. Do not describe the current statement as a complete
financial ledger before that integration is delivered and tested.

## Phase 4 — Inventory Engine (most critical)
**Build:** `stock_transactions`, `stock_balances`, posting service (the only writer), average-cost calculator, reservation lifecycle service, transfer, adjustment, physical count, stock ledger, current stock view.
**Screens:** Current Stock, Product Stock Ledger, Stock Transfer, Stock Adjustment, Physical Count.
**Exit:** invariant tests (balance = ledger sum), negative stock blocked, concurrent posting test, transfer atomicity.

**Progress:** The first Phase 4 slice establishes the append-only stock transaction ledger, the
posting service and its maintained product/warehouse balance projection, plus authenticated
current-stock and ledger read APIs. The Warehouse Stock screen displays named product/warehouse
rows with search, filtering, pagination, and permission gating. Stock transfers now post paired
`TRANSFER_OUT`/`TRANSFER_IN` ledger entries atomically, with central document numbering, audit, and
a permission-gated screen. Stock adjustments now post signed quantity lines atomically through the
inventory posting service, capture average cost, and have a permission-gated screen. The Product Stock Ledger screen now filters by product, warehouse, and
date, with running balances and links to transfer/adjustment source documents. The inventory-side
reservation service now supports reserve, partial release, and partial consume while keeping
reserved quantity separate from on-hand stock. A minimal sales-order/line persistence foundation
provides the real foreign-key target; quotation linkage and Sales workflow remain Phase 7 work.
Physical count sheets now snapshot each active stocked product in a warehouse, accept counted
quantities in partial updates, show variances, and post `COUNT_ADJUSTMENT` ledger movements
atomically. Posting rejects stale snapshots when stock or the stocked-product scope has changed.
The Phase 4 invariant and negative-stock tests pass. The concurrent-posting test also passed
against a separately migrated `sabuj_pran_test` database in a disposable MySQL 8.4 Docker
container on 2026-10-15; the shared application database was not used.

## Phase 5 — Purchase
**Build:** PO, goods receipt, direct purchase, purchase return, supplier due.
**Screens:** PO List, Create/Edit PO, PO Details, Goods Receive, Direct Purchase, Purchase Return.
**Exit:** receive raises stock, average cost and supplier due atomically; return reverses; PO status transitions tested.

**Progress:** Purchase Order drafts, Goods Receipt, credit-only Direct Purchase, and Purchase
Returns are implemented. Goods Receipt posting requires an approved or partially received PO and
enforces the configured receiving tolerance. Receipt and direct-purchase posting atomically update
stock ledger/balances, weighted-average cost, supplier due, audit logs, and document numbering.
Purchase Returns reference original Goods Receipt lines and atomically reverse stock and supplier
due at the original receipt cost. PO approval remains deferred to Phase 11.

## Phase 6 — Money & Simple Accounting
**Build:** money ledger, accounts balances, customer collection, supplier payment, expense, income, fund transfer, opening balances, cash book.
**Screens:** Account Balances & Ledger / Cash Book, Customer Collection, Supplier Payment, Expense Entry, Income Entry, Fund Transfer, Opening Balances (through money-account opening balances).
**Exit:** account balance invariant; collections reduce customer due; payments reduce supplier due; transfer writes two linked rows.

## Phase 7 — Sales
**Build:** quotation, sales order, integrate the Phase 4 reservation service with order lines, delivery (COGS), invoice, sales return, customer due, order tracking quantities, credit-limit check.
**Screens:** Quotation List, Create/Edit Quotation, Sales Order List, Create/Edit Sales Order, Sales Order Details, Delivery, Invoice List, Invoice Details/Print, Sales Return.
**Exit:** delivery from reserved/available stock cuts stock and records COGS; invoice raises due; collection clears it; tracking numbers correct. Shortage fulfillment through production orders is completed in Phase 8.

**Progress:** Quotation and Sales Order draft create/edit/list workflows are implemented with
server-calculated totals, central document numbering, audit, permissions, and simple screens. Sales
Orders now reserve and release stock through the Phase 4 inventory reservation service; an order
cannot be edited after reservation history exists. Delivery posting now consumes reserved/available
stock through the Phase 4 service, stores line-level COGS, and preserves the Sales Order status while
tracking delivered quantities. Invoices can now be posted once per delivery; they snapshot sales
prices and delivery COGS, increase customer due, and warn/block according to `credit_limit_mode`.
Quotations now transition from DRAFT to SENT and then to ACCEPTED or REJECTED. An ACCEPTED
quotation converts into one linked Sales Order; database uniqueness and row locking prevent a
second conversion. Sales Returns are posted against invoice lines, limited to the remaining invoiced
quantity, and atomically restock at the original COGS while reducing customer due by the
invoice-discounted return value. Order details expose Ordered, Available stock, Reserved, Produced,
Delivered, and Remaining quantities; available stock follows the inventory on-hand-minus-reserved
balance.

## Phase 8 — Production & Costing
**Build:** BOM, production order, consumption, output, cost calculation (materials at avg cost + labor + overhead), and sales-order shortage fulfillment.
**Screens:** BOM List, BOM Create/Edit, Production Order List, Create/Edit Production Order, Production Details & Costing.
**Exit:** raw stock falls, finished stock rises, finished-good average cost is correct, shortages are blocked, and eligible sales-order shortages can be linked to production orders.

**Progress:** BOM setup and the production-order lifecycle are implemented. Production orders use a
BOM and warehouse, check material availability when started, and atomically post raw-material
consumption, finished-goods output, audit, and weighted-average costing when completed. The
`/production-orders` screen supports draft editing, start/cancel, completion inputs, and costing
details. Backend API and UI tests cover the lifecycle and stock/cost effects. Sales-order shortage
linking uses a specific Sales Order line, validates that the BOM finished good and warehouse match,
updates the line's Produced quantity with audit in the same completion transaction, and rejects
output beyond the order line's unreserved, undelivered remaining quantity. Phase 8 exit checks pass.

## Phase 9 — Assets
**Build:** asset register, location assignment history with optional Phase 10 employee linkage,
maintenance log.
**Screens:** Asset List, Add/Edit, Location Assignment/Return, Maintenance History.
**Exit:** CRUD, employee/location assignment and maintenance history, permissions, audit, and
validation tests pass.

## Phase 10 — Employees
**Build:** employee master, user-account linkage, employee-linked asset assignment, attendance,
basic payroll, salary payment through Money. Use the shared `is_active`/`deleted_at` soft-delete
behavior for employee status.
**Screens:** Employee List, Employee Add/Edit, Attendance, Basic Payroll.
**Exit:** user accounts and asset assignments link only to valid employees; payroll totals are
correct and salary payment posts to the money ledger.

**Progress:** Employee Master and user-account linkage are implemented, with an optional employee
foreign key on user accounts. Phase 9 asset assignment history now optionally records the assigned
employee alongside its location. Attendance records one audited status per
employee/date, supports corrections, and provides `.xlsx` template, import, and date-range export.
Imports match employees by code, reject existing employee/date rows, and import valid rows while
reporting invalid or duplicate rows. Basic Payroll now snapshots active employees' monthly base
salaries, permits draft deductions, and posts each nonzero net salary to the Money ledger atomically.

## Phase 11 — Approvals
**Build:** approval rules, requests, actions, pending inbox, and hooks on PO / expense / adjustment. Invoice, payroll, and income approvals are outside the current Phase 11 scope.
**Screens:** Approval Rules, Pending Approvals.
**Exit:** matching document blocked until approved; self-approval blocked.

**Progress:** Approval rules, append-only request/action history, and a role-filtered pending inbox
are implemented. Matching POs wait for approval before they become APPROVED; matching expenses and
stock adjustments do not post money or stock effects until an approver decides. Approval decisions,
document status changes, and posting effects are atomic and audited. Requesters cannot approve their
own documents, and approval amounts are snapshotted for history. Rejection returns documents to an
editable draft; resubmission creates a new request. No matching rule preserves the normal flow.
Backend tests cover rule matching, all three hooks, role/self-approval checks, rejection/resubmission,
and rollback when posting fails.

## Phase 12 — Reports & Dashboard
**Build:** database views, report services, Report Center + Report Viewer, PDF/CSV export, management dashboard, readable invoice/statement print layouts.
**Screens:** Dashboard, Report Center, Report Viewer, Audit Log, Invoice Print, Party Statement Print.
**Exit:** dashboard figures reconcile with report totals; every report has seeded-data coverage.

**Progress:** Dashboard (`GET /api/v1/reports/dashboard` and `/`), the permission-protected Report
Center (`GET /api/v1/reports`), CSV export/browser print, and the read-only Audit Log screen are
implemented. Report types cover sales, purchases, stock valuation, low stock, customer/supplier due,
production cost, cash book, expense/income, profit, assets, and attendance/payroll. Report date,
party, product, and warehouse filters are supported where applicable. Dashboard and reports use
posted records/ledger data and are covered by API/UI tests. Seeded-data API tests cover every report
type. The dashboard reconciles to sales, purchases, collections, expenses, cash-book activity plus
account opening balances, current customer/supplier dues, stock valuation, profit, and pending-order
quantities in the order-status view. Current dashboard dues are compared with due reports as of
today; historical due reports remain end-date snapshots. Stock valuation includes inactive stocked
products that retain on-hand quantities, while low-stock reporting remains limited to active
products. The read-only stock, valuation, low-stock, party-due, account-balance,
order-status, profit-summary, and daily dashboard KPI views are added by migration
`20261111_reporting_views`; view calculations have seeded-data coverage.
Sales invoice history links to a read-only branded invoice layout with customer, product, delivery,
order, company, and amount details. Customer and supplier statements have branded browser-print/PDF
actions. Phase 12 exit criteria are covered by seeded report tests and dashboard reconciliation.

## Phase 13 — Hardening & Delivery
**Build:** full-cycle E2E test, seed/demo data, performance indexes, security review, README, API docs (OpenAPI), demo script, interview notes.
**Exit:** `docker compose up` + seed → run the full business cycle from the PRD with correct dashboard numbers.

---
## Per-module workflow (repeat for every module)
1. Read PRD section + rules + schema section.
2. Write/extend schema + Alembic migration.
3. Write failing tests (services, then API).
4. Implement service → repository → router.
5. Add permissions + audit hooks.
6. Build frontend screens (list, form, details) using the shared patterns.
7. Run lint, types, tests; commit.
8. Update docs; write a short own-words summary (interview prep).

## Risks
| Risk | Mitigation |
|---|---|
| AI-generated inconsistency | Module template, `CLAUDE.md`, one slice per prompt |
| Stock/money drift | Ledger-only writes, invariant tests |
| Unfamiliar Python | Learn the minimal set (type hints, Pydantic, SQLAlchemy sessions, FastAPI deps, pytest); AI explains each module |
| Scope size | Strict phase exit criteria; simplify HR/Assets UIs first |
