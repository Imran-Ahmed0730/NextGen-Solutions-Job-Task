# Interview Notes

Use these notes to explain the project in your own words. They are a concise review aid, not a
replacement for reading the implementation and requirements.

## 1. Project architecture

**Question: How is the application structured?**

Sabuj Pran is a modular monolith. The frontend is a Next.js App Router application. The backend is
one FastAPI application, organized by business module. A typical backend module separates router,
Pydantic schemas, service/business rules, repository access, SQLAlchemy models, and tests. Alembic
owns schema changes. Modules share one database and one deployment unit, which keeps the system
simple to build and operate while keeping business responsibilities organized.

**Question: Why a modular monolith instead of microservices?**

The ERP workflows need atomic changes across purchasing, inventory, costing, and money. One service
and database transaction make those posting operations straightforward to reason about. A
modular-monolith structure keeps boundaries without adding network failure modes, distributed
transactions, and deployment overhead that are not justified for this project's size.

**Question: Where does business logic live?**

Routers perform HTTP concerns: parse/validate requests, enforce dependencies, and serialize
responses. Services own business rules and transaction boundaries. Repositories centralize common
queries. Cross-module operations call the other module's service rather than editing its tables
directly.

## 2. Ledgers and invariants

**Question: How is stock represented?**

`stock_transactions` is the append-only movement ledger. The stock posting service writes signed
quantity movements and updates the corresponding balance in the same transaction. For each
product/warehouse pair, on-hand balance must equal the sum of signed ledger quantities. On-hand
stock cannot go negative for stocked products. Reservations reduce available quantity; they do not
change on-hand quantity.

**Question: How are money balances represented?**

`money_transactions` is the append-only account ledger. Every movement belongs to a money account.
The account balance equals its opening baseline plus signed transactions; overdraft behavior is
controlled per account. A transfer creates linked outflow and inflow rows in one database
transaction. Customer and supplier dues are derived from opening due and posted invoices, payments,
collections, and returns.

**Question: Why append-only ledgers?**

Posted financial/inventory events need an auditable explanation. Editing history would break
reconciliation and obscure what happened. Corrections are represented by linked returns,
reversals, or adjustments; projections such as current balances are updated transactionally and
can be checked against the ledger.

## 3. Costing and the business cycle

**Question: How does costing work?**

The system uses weighted-average product cost. A goods receipt recomputes average cost from the
previous stock quantity/cost and received quantity/cost. Production consumes materials at their
current average costs, adds labor and overhead, and divides by actual finished output. Delivery
stores COGS per invoice/delivery line at the average cost at delivery time; historical COGS is not
recomputed after later cost changes. Returns reverse using the original document's cost.

**Question: Walk through the complete business cycle.**

Create a supplier purchase order and receive raw material. Receipt posting writes stock transactions,
updates average cost, and raises supplier due atomically. Create a sales order, reserve available
stock, and fulfill a shortage with a linked production order. Production consumes raw materials and
posts finished output with calculated cost. Delivery reduces stock and stores COGS; invoicing raises
customer due. A collection writes a money transaction and reduces that due. Supplier payments,
returns, and expenses similarly update ledgers and dues through posting services. Statements and
the management dashboard summarize those posted events.

**Question: Why can an expense have approval status?**

An approval rule can hold a matching expense before its money effect is posted. Approval and ledger
posting occur within one transaction; failure rolls back both. When no rule matches, the expense is
posted with its money transaction so reports and dashboard totals reflect actual posted activity.

## 4. Approvals, security, and audit

**Question: How do approvals work?**

Approval rules match document type and amount. Matching documents wait in `PENDING_APPROVAL` and
cannot post until an eligible approver decides. The requester cannot approve their own document.
Decisions are append-only actions; rejection returns supported documents to editable drafts while
retaining request history.

**Question: How is endpoint access controlled?**

Protected endpoints require authentication and a granular `module.resource.action` permission.
The frontend may hide unavailable navigation, but the backend dependency is authoritative and
returns 403 on denial. Passwords are Argon2-hashed. Access JWTs use the configured secret and are
tied to persisted refresh sessions; refresh rotates the refresh token and logout revokes it.

**Question: What is audited?**

User, master-data, and document changes are recorded in append-only audit history with actor,
entity, action, and before/after values where applicable. Ledger transactions and approval actions
preserve business history rather than being edited in place.

## 5. Transactions, precision, and testing

**Question: How are posting failures handled?**

One database transaction encloses the document status change and all posting side effects.
Insufficient stock, invalid account balance, approval failure, or another rejected posting aborts
the transaction so there is no partial stock/money/document state.

**Question: How is numeric precision handled?**

Python `Decimal` and database `DECIMAL` are used for money and quantities; binary floating point is
avoided for accounting calculations. API schemas expose decimal values without requiring clients
to calculate financial results using floats.

**Question: What does the full-cycle test prove?**

The full-cycle API test builds an isolated SQLite database, drives the actual HTTP routes, and
checks purchase receipt, stock, average cost, reservation, linked production, delivery COGS,
invoice, collection, returns, supplier payment, expense, statements, balances, ledger invariants,
and dashboard reconciliation. It is a deterministic regression test; it does not replace verifying
the target MySQL deployment and running a UI demonstration.

## 6. Hardening and deployment status

Phase 13 adds the full-cycle regression, an idempotent demo master-data seed, report date-range
indexes, and safer date-bound report filtering. The security review identified a predictable
default JWT signing key; the default was removed and startup now requires a non-placeholder key of
at least 32 characters. Tests cover missing, placeholder, and short keys.

The repository's current Docker Compose setup is for development: it uses `next dev`, Uvicorn
reload, and publishes service ports. A written VPS guideline exists, but a reviewed production
Compose and frontend build configuration are still required before public deployment. Do not
describe the project as production-deployed until that work and a real server verification are
complete.

## 7. Suggested 60-second summary

“Sabuj Pran is a modular-monolith ERP-lite built with FastAPI, SQLAlchemy, Alembic, MySQL, and
Next.js. I organized backend code by business module and kept business rules in services. Inventory
and money use append-only ledgers with transactional posting, while balances are projections that
can be reconciled against those ledgers. Weighted-average costing supports purchasing and
production, and delivery stores COGS at posting time. Role permissions, approvals, audit history,
and a full-cycle API test protect the important workflows. The current Compose setup is a
development environment; production VPS deployment still needs a production configuration and
server validation.”
