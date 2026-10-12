# TO-DO

Legend: `[ ]` open · `[x]` done. Work top to bottom. Each phase's last item is its exit check.

## Open questions (do not let AI guess; decide and record)
- [ ] Credit-limit check: warn or block?
- [ ] Receiving tolerance over PO qty (percent)?
- [ ] Payroll scope: salary + deductions only, or allowances/overtime too?
- [ ] Invoice/report language: English only or English + Bangla?
- [ ] Warehouse-level or company-level average cost? (default: company-level)

## Phase 0 — Foundation
- [x] Create monorepo and git repository
- [x] Backend skeleton (FastAPI, settings, DB session, error handler)
- [x] Frontend skeleton (Next.js, TypeScript strict, Tailwind, shadcn/ui)
- [x] Docker compose (api, web, db) + `.env.example`
- [x] Alembic initialized, first empty migration
- [x] pytest + httpx set up; Vitest set up
- [x] ruff, formatter, mypy configured
- [x] CI pipeline (lint, types, tests, build)
- [x] `CLAUDE.md` created from `04_RULES.md`
- [x] Health endpoint + base layout page
- [x] Exit: stack boots, CI checks and builds pass locally

## Phase 1 — Auth & Security
- [ ] Models: users, roles, permissions, role_permissions, user_roles
- [ ] Password hashing, JWT access/refresh
- [ ] Login, logout, refresh endpoints
- [ ] Forgot/reset password, change password
- [ ] Permission dependency (`require("module.resource.action")`)
- [ ] Audit service + `audit_logs`
- [ ] Seed: admin user, base roles, permission catalog
- [ ] Screens: Login, Forgot Password, My Profile, Change Password
- [ ] Screens: User List, User Add/Edit, Roles, Permissions
- [ ] Permission-aware navigation
- [ ] Exit: 403 tests for every protected endpoint

## Phase 2 — Master Data
- [ ] `units` module (reference template for all others)
- [ ] Product categories
- [ ] Products (type, unit, category, stocked flag, reorder level)
- [ ] Price lists / product prices
- [ ] Warehouses
- [ ] Expense categories, income categories
- [ ] Payment methods, money accounts
- [ ] Company settings
- [ ] Document numbering service
- [ ] All Phase 2 screens
- [ ] Exit: CRUD, soft delete, permissions, audit tested

## Phase 3 — Customers & Suppliers
- [ ] Customer + supplier models, contacts
- [ ] Opening dues
- [ ] Statement service (running balance)
- [ ] Screens: lists, add/edit, statements (x2)
- [ ] Exit: statement math tested

## Phase 4 — Inventory Engine
- [ ] `stock_transactions`, `stock_balances`, reservations
- [ ] Posting service (single writer) + average-cost calculator
- [ ] Transfer, adjustment, physical count
- [ ] Stock ledger + current stock endpoints/views
- [ ] Screens: Current Stock, Stock Ledger, Transfer, Adjustment, Physical Count
- [ ] Invariant, negative-stock and concurrency tests
- [ ] Exit: all inventory invariants pass

## Phase 5 — Purchase
- [ ] PO + lines, status machine
- [ ] Goods receipt (post → stock + cost + due)
- [ ] Direct purchase
- [ ] Purchase return
- [ ] Screens: PO List, Create/Edit PO, PO Details, Goods Receive, Direct Purchase, Purchase Return
- [ ] Exit: receive/return atomicity tested

## Phase 6 — Money
- [ ] `money_transactions` + balance service
- [ ] Customer collection, supplier payment
- [ ] Expense, income
- [ ] Fund transfer, opening balances
- [ ] Account ledger / cash book
- [ ] Screens: 8 Money screens
- [ ] Exit: account and due invariants pass

## Phase 7 — Production
- [ ] BOM + lines
- [ ] Production order (draft → in progress → completed)
- [ ] Consumption + output posting through inventory service
- [ ] Cost calculation (materials + labor + overhead)
- [ ] Screens: 5 Production screens
- [ ] Exit: cost and stock effects tested

## Phase 8 — Sales
- [ ] Quotation, sales order (+ convert quotation → order)
- [ ] Reservation
- [ ] Link order shortage → production order
- [ ] Delivery with COGS
- [ ] Invoice, customer due, credit-limit check
- [ ] Sales return
- [ ] Order tracking (Ordered/Available/Reserved/Produced/Delivered/Remaining)
- [ ] Screens: 9 Sales screens
- [ ] Exit: stock + COGS + due tested together

## Phase 9 — Assets
- [ ] Asset, assignment, maintenance models + services
- [ ] Screens: Asset List, Add/Edit, Assignment & Maintenance

## Phase 10 — Employees
- [ ] Employee master
- [ ] Attendance
- [ ] Payroll + salary payment via Money
- [ ] Screens: Employee List, Add/Edit, Attendance, Basic Payroll

## Phase 11 — Approvals
- [ ] Rules, requests, actions
- [ ] Hooks: PO, expense, adjustment
- [ ] Screens: Approval Rules, Pending Approvals
- [ ] Exit: block-until-approved and self-approval tests

## Phase 12 — Reports & Dashboard
- [ ] DB views (stock, due, balances, profit, KPIs)
- [ ] Report services + Report Center/Viewer
- [ ] PDF/CSV export + print layouts (invoice, statements)
- [ ] Management dashboard (11 KPIs)
- [ ] Audit Log screen
- [ ] Exit: dashboard = report totals

## Phase 13 — Hardening
- [ ] Full-cycle E2E test
- [ ] Seed/demo data script
- [ ] Indexes + performance check
- [ ] Security review
- [ ] README, OpenAPI docs, demo script
- [ ] Interview notes: architecture, ledger design, costing, transaction flow
