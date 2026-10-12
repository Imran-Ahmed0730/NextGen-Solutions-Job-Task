# PROJECT — Business Management Software (Sabuj Pran)

## 1. Overview
A web-based business management system (ERP-lite) for **Sabuj Pran**, a small manufacturing/trading company with 10–20 employees. It replaces manual records with one system that gives management reliable answers about stock, orders, sales, purchases, dues, cash/bank/mobile-banking balances, expenses and profit.

Source: *Software Development Plan & Technical Implementation Blueprint* (NextGen IT Ltd, "AI_SoftwareDevelopmentPractice_v02_Monolith").

## 2. Goals
- Run the full business cycle reliably:
  `Supplier → Raw Material Purchase → Stock → Production → Sale → Customer Due → Collection → Cash/Bank/MFS → Expense → Management Dashboard`
- Provide one source of truth for stock and money (ledger-based, auditable).
- Give management a real-time role-based dashboard and reports.
- Be maintainable by a small team, built with AI assistance under strict, documented rules.

## 3. Non-goals
- No microservices (modular monolith only).
- No tax/VAT handling.
- No full double-entry general ledger (simple money accounting only).
- No stored procedures/triggers for business logic (logic lives in Python services).

## 4. Architecture decision
**Modular monolith**: one deployable application, split into clear internal modules. Modules communicate only through service-layer functions, never by reading each other's tables directly. Can be split into services later if needed.

## 5. Modules (15)
1. Authentication & Users
2. Company Setup
3. Products & Pricing
4. Customers
5. Suppliers
6. Sales
7. Purchase
8. Inventory
9. Production
10. Money & Simple Accounting
11. Assets
12. Employees
13. Approvals
14. Reports
15. Audit & Administration

## 6. Success criteria
The project succeeds when the complete cycle above runs end to end with correct numbers, and management can trust the answers on: stock, orders, sales, purchase, customer due, supplier due, cash, bank, mobile banking, expenses, profit.

## 7. Context
This is also a **job-interview deliverable**. The tech stack is fixed and cannot change. The developer's primary background is PHP/Laravel, so Python/FastAPI code is AI-assisted and must be understood and explainable by the developer.

## 8. Guiding principle
> The requirement wins. AI is the development assistant. It is not the owner of the business rules.

## 9. Document map
| File | Purpose |
|---|---|
| 01_PROJECT.md | This overview |
| 02_TECH_STACK.md | Technologies and structure |
| 03_PRD.md | Product requirements |
| 04_RULES.md | Business + engineering + AI rules |
| 05_PLAN.md | Phased development plan |
| 06_TODO.md | Task checklist |
| 07_DESIGN.md | UI/UX design guide |
| 08_APP_FLOW.md | Screen and process flows |
| 09_SCHEMA.md | Database schema |
