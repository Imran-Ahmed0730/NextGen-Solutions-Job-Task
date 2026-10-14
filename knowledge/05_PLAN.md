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
Physical counts and the Phase 4 concurrency exit tests remain open.

## Phase 5 — Purchase
**Build:** PO, goods receipt, direct purchase, purchase return, supplier due.
**Screens:** PO List, Create/Edit PO, PO Details, Goods Receive, Direct Purchase, Purchase Return.
**Exit:** receive raises stock, average cost and supplier due atomically; return reverses; PO status transitions tested.

## Phase 6 — Money & Simple Accounting
**Build:** money ledger, accounts balances, customer collection, supplier payment, expense, income, fund transfer, opening balances, cash book.
**Screens:** Account Balances, Customer Collection, Supplier Payment, Expense Entry, Income Entry, Fund Transfer, Opening Balances, Account Ledger / Cash Book.
**Exit:** account balance invariant; collections reduce customer due; payments reduce supplier due; transfer writes two linked rows.

## Phase 7 — Sales
**Build:** quotation, sales order, integrate the Phase 4 reservation service with order lines, delivery (COGS), invoice, sales return, customer due, order tracking quantities, credit-limit check.
**Screens:** Quotation List, Create/Edit Quotation, Sales Order List, Create/Edit Sales Order, Sales Order Details, Delivery, Invoice List, Invoice Details/Print, Sales Return.
**Exit:** delivery from reserved/available stock cuts stock and records COGS; invoice raises due; collection clears it; tracking numbers correct. Shortage fulfillment through production orders is completed in Phase 8.

## Phase 8 — Production & Costing
**Build:** BOM, production order, consumption, output, cost calculation (materials at avg cost + labor + overhead), and sales-order shortage fulfillment.
**Screens:** BOM List, BOM Create/Edit, Production Order List, Create/Edit Production Order, Production Details & Costing.
**Exit:** raw stock falls, finished stock rises, finished-good average cost is correct, shortages are blocked, and eligible sales-order shortages can be linked to production orders.

## Phase 9 — Assets
**Build:** asset register, assignment, maintenance.
**Screens:** Asset List, Asset Add/Edit, Asset Assignment & Maintenance.
**Exit:** CRUD, history, permissions, audit.

## Phase 10 — Employees
**Build:** employee master, attendance, basic payroll, salary payment through Money.
**Screens:** Employee List, Employee Add/Edit, Attendance, Basic Payroll.
**Exit:** payroll totals correct; salary payment posts to money ledger.

## Phase 11 — Approvals
**Build:** approval rules, requests, actions, pending inbox, hooks on PO / expense / adjustment / (optionally invoice, payroll).
**Screens:** Approval Rules, Pending Approvals.
**Exit:** matching document blocked until approved; self-approval blocked.

## Phase 12 — Reports & Dashboard
**Build:** database views, report services, Report Center + Report Viewer, PDF/CSV export, management dashboard.
**Screens:** Dashboard, Report Center, Report Viewer, Audit Log.
**Exit:** dashboard figures equal report totals; every report has a test with seeded data.

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
