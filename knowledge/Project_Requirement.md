# Sabuj Pran Business Management Software

## Technical implementation blueprint

This document summarizes the technical direction, screen inventory, delivery phases, and project
success criteria for the Sabuj Pran ERP-lite application. It is a planning blueprint, not a
substitute for the detailed functional requirements or binding business rules.

## 1. Requirements authority

Use these documents in this order when content conflicts:

1. `04_RULES.md` for binding business, engineering, and AI-use rules.
2. `03_PRD.md` for product behavior and acceptance requirements.
3. `09_SCHEMA.md` for the planned data model.
4. This blueprint, `05_PLAN.md`, and `08_APP_FLOW.md` for implementation planning and screen flows.
5. `10_DEVELOPMENT_GUIDE.md` for what is implemented today; it does not override requirements.

Unknown business behavior must be recorded in `06_TODO.md` and confirmed by the requirement owner.

## 2. Purpose and architecture

The system replaces manual records for a small manufacturing and trading company with a single
auditable application. Its target business cycle is:

```text
Supplier -> Purchase -> Inventory -> Sales Order -> Production (if needed) -> Delivery/Sale
         -> Customer Due -> Collection -> Cash/Bank/MFS -> Expense -> Dashboard
```

Use a **modular monolith**: one deployable backend and frontend, separated internally by business
module. Modules communicate through service-layer functions rather than direct cross-module table
access. Do not introduce microservices for the current scope.

Major modules:

1. Authentication and users
2. Company setup
3. Products and pricing
4. Customers
5. Suppliers
6. Sales
7. Purchase
8. Inventory
9. Production
10. Money and simple accounting
11. Assets
12. Employees
13. Approvals
14. Reports
15. Audit and administration

Business rules belong in FastAPI services. The frontend handles data entry, display, workflow, and
validation feedback; backend validation remains authoritative.

## 3. Technology direction

The project uses the fixed stack recorded in `02_TECH_STACK.md`:

- Frontend: Next.js App Router, React, TypeScript, Tailwind CSS, and Zod.
- Backend: FastAPI, Python, Pydantic, and SQLAlchemy.
- Database: MySQL with Alembic migrations.
- Tests and quality: pytest, Vitest, Ruff, mypy, and TypeScript checks.
- Local orchestration: Docker Compose.

Suggested supporting frontend capabilities include accessible shared components, server-state
management, form helpers, charts, date utilities, and print/export tooling. Add them only where a
feature requires them and in accordance with the fixed stack and repository conventions.

## 4. Screen inventory

The detailed navigation and workflows are maintained in `08_APP_FLOW.md`. The earlier estimate of
38 screens omitted whole functional areas. The current planning estimate is approximately 71,
counting route/screen concepts as follows:

| Area | Approximate screens |
|---|---:|
| Login and profile | 4 |
| Dashboard | 1 |
| Master data and setup | 10 |
| Customers and suppliers | 6 |
| Purchase | 6 |
| Inventory | 5 |
| Production | 5 |
| Sales | 9 |
| Money | 8 |
| Assets | 3 |
| Employees | 4 |
| Administration | 8 |
| Reports | 2 |
| **Total** | **71** |

The estimate includes list and add/edit/detail workflows where appropriate; it is not a requirement
to create a separate route for every modal or action. Required areas include:

- **Login/profile:** login, password recovery/reset, profile, and password change.
- **Dashboard:** role/permission-aware management KPIs.
- **Master data:** products, categories, units, prices, warehouses, expense/income categories,
  payment methods, money accounts, company settings, and document numbering.
- **Customers/suppliers:** list, add/edit, additional contacts, opening dues, and statements.
- **Inventory:** current stock, product ledger, transfer, adjustment, and physical count.
- **Transactions:** purchase, money, production, and sales flows as detailed in the PRD and app
  flow.
- **Administration/reports:** users, roles, permissions, approvals, audit, configuration, report
  center, and report viewer.

Screens and actions are permission-aware; API authorization is mandatory even when an action is
hidden from the UI.

## 5. Delivery phases and dependencies

Follow the ordered roadmap in `05_PLAN.md`; phases are not considered complete until their exit
criteria and tests pass.

| Phase | Scope |
|---|---|
| 0 | Repository, application skeleton, configuration, database/migrations, test and CI foundation |
| 1 | Authentication, users, roles, permissions, sessions, profile, password flows, audit foundation |
| 2 | Master data, company settings, and document numbering |
| 3 | Customer/supplier masters, contacts, opening dues, and opening-balance statements |
| 4 | Inventory ledger, balances, reservations, transfers, adjustments, counts, and stock views |
| 5 | Purchase orders, receipts, direct purchases, supplier due effects, and returns |
| 6 | Money accounts and ledger, collections, payments, expenses, income, transfers, opening balances |
| 7 | Quotations, sales orders, reservations, delivery, invoices, returns, and customer dues |
| 8 | BOM, production orders, material consumption, output, production costing, and sales-order shortage fulfillment |
| 9 | Asset register, assignment, and maintenance |
| 10 | Employee master, attendance, and basic payroll |
| 11 | Approval rules, requests, decisions, and posting gates |
| 12 | Reports, exports/print, dashboard, and audit-log screen |
| 13 | Full-cycle testing, performance/security hardening, delivery documentation, and demo |

The AI software-development practice roadmap explicitly numbers phases through Phase 7 (Sales) but
does not assign Production a phase. Production remains required by `03_PRD.md` and `09_SCHEMA.md`;
Phase 8 in this supporting plan is a supplemental implementation phase for that required scope.

Inventory precedes purchase, sales, and production. Sales orders and reservations are implemented
in Phase 7; Phase 8 production can then link production orders to sales-order shortages. Money
workflows precede complete party statement integration. Phase 3 statements initially contain the
opening-balance line; later purchase, sales, return, collection, and payment postings extend those
statements in their own phases. Do not claim the current opening-only statement is a complete
financial ledger.

## 6. Testing and completion

Each module must follow the engineering rules in `04_RULES.md`: validated requests, permissions,
audit where applicable, migration when the schema changes, and tests for service behavior,
failure paths, API access denial, and relevant invariants.

The project is successful when a seeded full-cycle test can run the business workflow with correct
stock, party dues, money balances, cost of goods sold, expenses, and dashboard/report totals.
Management must be able to obtain reliable answers about:

- Stock, valuation, and order status
- Sales, purchases, and production cost
- Customer and supplier dues
- Cash, bank, and mobile financial service balances
- Expenses and estimated profit

## 7. Binding principle

> Requirements and business rules win. AI tools assist implementation; they do not decide business
> behavior.
