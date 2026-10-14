# TO-DO

Legend: `[ ]` open · `[x]` done. Work top to bottom. Each phase's last item is its exit check.

## Open questions (do not let AI guess; decide and record)
- [ ] Credit-limit check: warn or block?
- [ ] Receiving tolerance over PO qty (percent)?
- [ ] Payroll scope: salary + deductions only, or allowances/overtime too?
- [ ] Invoice/report language: English only or English + Bangla?
- [ ] Warehouse-level or company-level average cost? (default: company-level)
- [ ] Password minimum length/complexity policy? (Current implementation requires at least 8 characters.)

## Decisions made
- Password recovery uses one-time reset links sent to the user's registered email address.
- Lock an account for 15 minutes after 5 consecutive failed login attempts.

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
- [x] Models: users, roles, permissions, role_permissions, user_roles, refresh_tokens, password_resets, audit_logs
- [x] Password hashing, revocable JWT access and rotating refresh sessions
- [x] Login, logout, refresh endpoints
- [x] Email-based forgot/reset flow, change password
- [x] Permission dependency (`require_permission("module.resource.action")`)
- [x] Audit service + append-only `audit_logs`
- [x] Seed: admin user, Administrator role, permission catalog
- [x] Screens: Login, Forgot Password, My Profile, Change Password
- [x] Screens: User List, User Add/Edit, Roles, Permissions
- [x] Permission-aware navigation
- [x] Exit: 403 tests for every protected endpoint

## Phase 2 — Master Data
- [x] `units` module (reference template for all others)
- [x] Product categories
- [x] Products (type, unit, category, stocked flag, reorder level)
- [x] Price lists / product prices
- [x] Warehouses
- [x] Expense categories, income categories
- [x] Payment methods, money accounts
- [x] Company settings
- [x] Document numbering service
- [x] All Phase 2 screens
- [x] Exit: CRUD, validation, permissions, audit, gap-free numbering tested

## Phase 3 — Customers & Suppliers
- [x] Customer + supplier models, contacts
- [x] Opening dues
- [x] Opening-balance statement entry and running balance
- [x] Screens: customer/supplier lists and add/edit
- [x] Screens: customer/supplier statements
- [x] Customer/supplier contact management screens
- [x] Search, pagination, input validation, and permission denial coverage
- [x] Exit: party/contact CRUD, audit, permissions, and opening-balance statement behavior tested
- [ ] Extend customer statements with posted invoices, returns, and collections (Phase 6/8)
- [ ] Extend supplier statements with posted purchases, returns, and payments (Phase 5/6)

## Phase 4 — Inventory Engine
- [x] `stock_transactions` and `stock_balances` schema and migration
- [x] Single stock-posting service writes the ledger and updates balances atomically
- [x] Weighted-average cost calculation helper
- [x] Current stock and stock ledger read APIs with permission checks
- [x] Warehouse Stock screen with product search, warehouse filtering, pagination, and permission gating
- [ ] Reservations and reservation lifecycle service
- [ ] Transfer, adjustment, physical count
- [ ] Screens: Product Stock Ledger, Transfer, Adjustment, Physical Count
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
- [ ] Add `users.employee_id` foreign key to `employees.id`
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
