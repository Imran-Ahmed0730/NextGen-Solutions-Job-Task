# RULES

Three groups: **Business rules** (the requirement wins), **Engineering rules**, **AI usage rules**. Keep a copy of this file in `CLAUDE.md` and give it to the AI in every session.

## A. Business rules

### Inventory
- B-INV-1: Stock changes **only** through the stock posting service, which writes an append-only `stock_transactions` row. Nothing edits `stock_balances` directly.
- B-INV-2: Movement types: `PURCHASE_RECEIPT, PURCHASE_RETURN, PRODUCTION_CONSUME, PRODUCTION_OUTPUT, SALE_DELIVERY, SALE_RETURN, TRANSFER_OUT, TRANSFER_IN, ADJUSTMENT_IN, ADJUSTMENT_OUT, COUNT_ADJUSTMENT, OPENING`.
- B-INV-3: On-hand stock may never go negative (unless a product is flagged non-stocked).
- B-INV-4: Available = On-hand − Reserved. Reservation reduces available, not on-hand.
- B-INV-5: Invariant: `stock_balances.qty == SUM(stock_transactions.qty_signed)` per product + warehouse.

### Costing
- B-COST-1: Weighted average cost per product.
- B-COST-2: Goods receipt: `new_avg = (old_qty*old_avg + recv_qty*unit_cost) / (old_qty + recv_qty)`.
- B-COST-3: Production consumes materials at current average cost; finished-good unit cost = (materials + labor + overhead) / actual output qty, then updates the finished good's average cost.
- B-COST-4: Delivery records COGS = qty × average cost at delivery time (stored on the delivery line, never recomputed).
- B-COST-5: Purchase/sale returns reverse at the original document's cost.
- B-COST-6: No tax/VAT anywhere.

### Purchase
- B-PUR-1: PO has statuses `DRAFT, PENDING_APPROVAL, APPROVED, PARTIALLY_RECEIVED, RECEIVED, CLOSED, CANCELLED`.
- B-PUR-2: Receiving cannot exceed ordered qty by more than a configurable tolerance.
- B-PUR-3: Posting a goods receipt / direct purchase: stock ledger + average cost + supplier due, atomically.
- B-PUR-4: Purchase return: reduces stock and supplier due; qty cannot exceed received qty.

### Sales
- B-SAL-1: Flow: Quotation → Sales Order → Reservation → (Production) → Delivery → Invoice → Return.
- B-SAL-2: Order tracking quantities: Ordered, Available, Reserved, Produced, Delivered, Remaining (= Ordered − Delivered).
- B-SAL-3: Delivery reduces stock and records COGS; cannot deliver more than ordered (+ tolerance) or more than available.
- B-SAL-4: Invoice posting raises customer due. Credit-limit check on order/invoice (warn or block by setting).
- B-SAL-5: Sales return qty cannot exceed delivered qty; restocks at original COGS and reduces customer due.

### Money
- B-MON-1: Every money movement is an append-only `money_transactions` row against a money account (Cash/Bank/MFS).
- B-MON-2: Customer due = opening due + posted invoices − collections − returns. Supplier due is symmetric.
- B-MON-3: Fund transfer writes two linked rows (out + in) in one transaction.
- B-MON-4: Cash/bank account balance may not go negative unless account allows overdraft.
- B-MON-5: Invariant: `account balance == opening + SUM(money_transactions.amount_signed)`.

### Documents & status
- B-DOC-1: Posted documents are immutable. Corrections use returns, reversals or adjustments.
- B-DOC-2: Document numbers come only from the central numbering service (prefix + year + sequence, per type, gap-free for posted docs).
- B-DOC-3: Master data uses soft delete (`is_active`, `deleted_at`); referenced records can't be hard-deleted.

### Approvals & audit
- B-APP-1: If an approval rule matches (document type + amount threshold), the document goes to `PENDING_APPROVAL` and cannot post until approved.
- B-APP-2: Requester cannot approve their own document.
- B-AUD-1: Every create/update/delete/status change writes an `audit_logs` row (user, time, entity, id, action, before/after JSON). Audit logs are never edited or deleted.

### Security
- B-SEC-1: Every endpoint requires auth and a permission (`module.resource.action`) except login/forgot password.
- B-SEC-2: Passwords hashed (argon2/bcrypt); lock account after repeated failures.
- B-SEC-3: Admin cannot remove their own last admin role.

## B. Engineering rules

- E-1: **Modular monolith.** Each module has `router, schemas, models, service, repository, tests`. Same layout for every module (copy the `units` module as the template).
- E-2: Routers contain no business logic. Services own business rules and transactions.
- E-3: Cross-module access only through the other module's service.
- E-4: One DB transaction per posting operation; roll back everything on failure.
- E-5: `DECIMAL` for money (18,2) and quantity (18,3). No floats.
- E-6: Type hints everywhere; mypy and ruff must pass.
- E-7: Validate all input independently in both the frontend (Zod) and backend (Pydantic). Frontend validation improves UX; backend validation is mandatory and authoritative. Keep rules consistent, but never rely on frontend validation for security or data integrity.
- E-8: Migrations only via Alembic; never edit the DB by hand; never edit an applied migration.
- E-9: Naming: tables `snake_case` plural; columns `snake_case`; Python `snake_case`; React components `PascalCase`; files in frontend `kebab-case`.
- E-10: Standard error codes (e.g. `STOCK_INSUFFICIENT`, `PERMISSION_DENIED`, `DOCUMENT_POSTED`, `VALIDATION_ERROR`).
- E-11: Every service function that changes data is covered by tests, including failure paths.
- E-12: Required tests: unit (services), API (incl. permission denial), invariants, and the full-cycle E2E.
- E-13: No secrets in code; config via environment variables.
- E-14: Small commits, one slice each; message format `module: what changed`.
- E-15: A feature is done only when: code + migration + tests pass + permission added + audit hook + docs updated.
- E-16: Always write codes in optimized way and reuse the code instead of duplicating code.
- E-17: Create/update documentation for every part
- E-18: Commit after completing a part or module so that it can be rolled back easily to a certain module.
- E-19: Show a visible asterisk (`*`) beside every required field's visible label, including fields in dynamic rows and table/grid headers. Keep the marker consistent with frontend and backend validation; never mark optional fields as required.
- Whenever a permission is added it must be assigned to admin

## C. AI usage rules

- AI-1: The requirement documents win. If AI output conflicts with `03_PRD.md` or the business rules, the AI is wrong.
- AI-2: Always give the AI `CLAUDE.md`, the relevant module spec, and the schema section before asking for code.
- AI-3: One slice per prompt: model → migration → schema → service → router → tests → UI. No sweeping multi-module prompts.
- AI-4: Ask the AI to copy the existing module pattern; do not accept new styles, libraries or folder layouts.
- AI-5: For risky logic (stock, costing, money, approvals) write tests first, then code to pass them.
- AI-6: Never accept code without running tests, linters and type checks yourself.
- AI-7: Do not let the AI invent business rules, columns or endpoints. Unknowns go back to the requirement owner (log in `06_TODO.md` as an open question).
- AI-8: After each module, have the AI explain the code, then summarize it in your own words (interview readiness).
- AI-9: Review diffs before committing; reject unrelated changes the AI made.
- AI-10: Never paste secrets or real customer data into AI tools.
