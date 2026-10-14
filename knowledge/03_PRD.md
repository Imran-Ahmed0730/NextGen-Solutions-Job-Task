# PRD — Product Requirements Document

## 1. Users and roles
| Role | Typical user | Main needs |
|---|---|---|
| Owner / Management | Owner | Dashboard, all reports, approvals |
| Admin | System admin | Users, roles, permissions, config, audit |
| Sales | Sales staff | Customers, quotations, orders, delivery, invoices |
| Purchase | Purchase staff | Suppliers, POs, receiving |
| Store / Inventory | Storekeeper | Stock, transfer, adjustment, count |
| Production | Production supervisor | BOM, production orders |
| Accounts | Accountant | Money, collections, payments, expenses, reports |
| HR | HR staff | Employees, attendance, payroll |
Roles are configurable; permissions are granular (`module.resource.action`).

## 2. Functional requirements

### FR-1 Authentication & Users
Login (username/email/mobile + password), session management, forgot/reset password, my profile, change password, user CRUD, roles, permissions.

### FR-2 Company Setup
Company info, currency, timezone, invoice settings, document numbering.

### FR-3 Products & Pricing
Products (raw material / finished good / trading), categories, units (KG, Piece, Roll, Block…), price lists, search/filter.

### FR-4 Customers & FR-5 Suppliers
Customer and supplier master data, multiple contact records, opening dues, searchable and
paginated lists, and statements with running balances. Until purchase, sales, and money posting
workflows exist, statements show the opening-balance entry only; later phases must add posted
documents, returns, collections, and payments to the appropriate party statements.

### FR-6 Purchase
Purchase Order (draft → approved → partially/fully received → closed), Goods Receive, Direct Purchase, Purchase Return. Each receive updates stock, average cost and supplier due.

### FR-7 Inventory
Stock transaction ledger, stock balance per product/warehouse, transfer between warehouses, adjustment, physical count, stock ledger, current stock view. Negative stock blocked.

### FR-8 Production
Bill of Materials (recipe), production order, raw material consumption, finished-goods output, **production cost calculation** (raw materials at average cost + optional labor/overhead ÷ output qty). Finished-good cost feeds cost of goods sold.

### FR-9 Sales
Quotation → Sales Order → Reservation → Production (if needed) → Delivery → Invoice → Sales Return. Order detail shows: Ordered / Available / Reserved / Produced / Delivered / Remaining. Delivery reduces stock and records cost of goods sold. Invoice raises customer due.

### FR-10 Money & Simple Accounting
Accounts: Cash, Bank, MFS (bKash/Nagad, etc.). Customer collection, supplier payment, expense, income, fund transfer, opening balances, account ledger / cash book.

### FR-11 Assets
Asset register, assignment to employees/locations, maintenance log.

### FR-12 Employees
Employee master, attendance, basic payroll (monthly salary, deductions, payment through Money).

### FR-13 Approvals
Configurable approval rules (document type, amount threshold, approver role). Pending approvals inbox. Documents under approval cannot post until approved.

### FR-14 Reports
Report Center with parameterized reports (date range, party, product, warehouse): sales, purchase, stock and valuation, low stock, customer/supplier due and aging, statements, production cost, cash book, expense, income, profit, assets, attendance/payroll, audit log. Export to PDF/CSV, print.

### FR-15 Audit & Administration
Immutable audit log of create/update/delete/status changes (who, when, before/after). Document numbering configuration.

### FR-16 Dashboard (Owner/Management)
Today's Sales, Collection, Expenses, Purchase; Cash, Bank, MFS balances; Customer Due, Supplier Due; Inventory Value; Pending Orders; Estimated Profit.

## 3. Screens (approximately 71)
| Area | Count |
|---|---|
| Login & Profile | 4 |
| Dashboard | 1 |
| Master Data & Setup | 10 |
| Customer & Supplier | 6 |
| Purchase | 6 |
| Inventory | 5 |
| Production | 5 |
| Sales | 9 |
| Money | 8 |
| Assets | 3 |
| Employees | 4 |
| Administration | 8 |
| Reports | 2 |
Full list in `08_APP_FLOW.md`.

## 4. Non-functional requirements
- **Correctness:** stock and money ledgers must always reconcile (invariants tested).
- **Security:** RBAC on every endpoint, password hashing, JWT expiry/refresh, input validation, SQL injection safe via ORM, audit trail.
- **Performance:** list pages < 1s for 100k rows with pagination/indexes.
- **Usability:** works on desktop first, usable on tablet; Bangla/English-ready (labels in a translation file; English first).
- **Reliability:** every posting is one DB transaction; posted documents are immutable.
- **Maintainability:** modular monolith, one module template, tests per module.
- **Deployability:** `docker compose up` runs the whole system with seed data.

## 5. Costing (decided)
- Weighted average cost per product (per company, not per warehouse).
- Raw material avg cost updates on each goods receipt.
- Production consumes raw material at current avg cost; finished-good cost = (materials + labor + overhead) ÷ actual output qty.
- Delivery records COGS at the product's avg cost at that moment.
- **Estimated profit** = sales − COGS − expenses (period). No tax/VAT.

## 6. Out of scope
Tax/VAT, multi-currency, multi-company, full general ledger, e-commerce, mobile native app, payment gateway integration.

## 7. Acceptance (summary)
1. Full-cycle end-to-end test passes with seeded data.
2. Invariant tests pass (stock = ledger sum, account balance = money ledger sum, due = documents − payments).
3. Every endpoint enforces permissions; denial tests exist.
4. Dashboard numbers match report totals.
