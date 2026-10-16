# DATABASE SCHEMA (MySQL 8, InnoDB, utf8mb4)

## Conventions
- Table names: `snake_case`, plural. PK: `id BIGINT UNSIGNED AUTO_INCREMENT`.
- Money `DECIMAL(18,2)`, quantity `DECIMAL(18,3)`, unit cost `DECIMAL(18,4)`.
- Audit columns on most tables: `created_at, updated_at, created_by, updated_by`.
- Master tables add `is_active TINYINT(1)` and `deleted_at DATETIME NULL` (soft delete).
- Documents have `doc_no VARCHAR(30) UNIQUE`, `status`, `doc_date`, and optional `approval_request_id`.
- Foreign keys everywhere; indexes on FKs, `doc_date`, `status`, and (product_id, warehouse_id).
- Ledger tables (`stock_transactions`, `money_transactions`, `audit_logs`) are append-only.
- `(PK)` primary key, `(FK→table)` foreign key, `(U)` unique.

---
## 1. Auth & Admin
**users**: id, username(U), email(U, null), mobile(U, null), password_hash, full_name, employee_id(FK→employees, null), is_active, last_login_at, failed_attempts, locked_until
**roles**: id, name(U), description, is_active
**permissions**: id, code(U) e.g. `sales.invoice.post`, module, description
**role_permissions**: role_id(FK), permission_id(FK) (PK both)
**user_roles**: user_id(FK), role_id(FK) (PK both)
**refresh_tokens**: id, user_id(FK), token_hash, expires_at, revoked_at
**password_resets**: id, user_id(FK), token_hash, expires_at, used_at
**audit_logs**: id, user_id(FK→users, null), entity_type, entity_id, action(CREATE/UPDATE/DELETE/STATUS/LOGIN), before_json, after_json, ip, created_at
**document_sequences**: id, doc_type(U with year), prefix, year, last_number, padding
**company_settings**: key (PK), value. Seeded keys: `company_name`, `company_address`,
`company_phone`, `company_email`, `currency_code`, `timezone`, `invoice_footer`,
`credit_limit_mode` (`WARN`/`BLOCK`), and `receipt_tolerance_pct`. The key/value store permits
additional settings; invoice rendering and purchase/sales policy enforcement are implemented with
their respective transaction workflows.

## 2. Master Data
**units**: id, name, code(U), allow_decimal
**product_categories**: id, name, parent_id(FK→self, null)
**products**: id, sku(U), name, type(RAW/FINISHED/TRADING), category_id(FK), unit_id(FK), is_stocked, reorder_level, avg_cost(DECIMAL 18,4), sales_price_default, description
**price_lists**: id, name, is_default, valid_from, valid_to
**product_prices**: id, price_list_id(FK), product_id(FK), price, (U price_list_id+product_id)
**warehouses**: id, name, code(U), address, is_default
**expense_categories**: id, name, parent_id(null)
**income_categories**: id, name
**payment_methods**: id, name, type(CASH/BANK/MFS/ONLINE)
**money_accounts**: id, name, type(CASH/BANK/MFS), payment_method_id(FK), account_no(null), opening_balance, allow_overdraft

## 3. Parties
**customers**: id, code(U), name, mobile, email, address, credit_limit, opening_due, price_list_id(FK, null)
**suppliers**: id, code(U), name, mobile, email, address, opening_due
**party_contacts**: id, party_type(CUSTOMER/SUPPLIER), party_id, name, phone, email, designation

## 4. Inventory
**stock_transactions** (ledger, append-only): id, txn_date, product_id(FK), warehouse_id(FK), movement_type, qty_signed, unit_cost, source_type, source_id, source_line_id, note, created_by, created_at
**stock_balances**: product_id(FK), warehouse_id(FK) (PK both), qty_on_hand, qty_reserved, updated_at
**stock_reservations**: id, sales_order_line_id(FK), product_id, warehouse_id, qty, qty_consumed, qty_released, status(ACTIVE/RELEASED/CONSUMED). `qty_consumed` and `qty_released` preserve partial lifecycle history; active quantity is `qty - qty_consumed - qty_released`. Reserve/release affect available stock only; consume reduces reserved quantity, increments the order line's delivered quantity, and posts a `SALE_DELIVERY` ledger movement at current average cost.
**stock_transfers**: id, doc_no, doc_date, from_warehouse_id, to_warehouse_id, status, note
**stock_transfer_lines**: id, transfer_id(FK), product_id, qty
**stock_adjustments**: id, doc_no, doc_date, warehouse_id, reason, status
**stock_adjustment_lines**: id, adjustment_id(FK), product_id, qty_signed, unit_cost
**physical_counts**: id, doc_no(nullable until posted), count_date, warehouse_id, status(OPEN/COUNTED/POSTED), created_by, posted_by, posted_at
**physical_count_lines**: id, count_id(FK), product_id, system_qty(snapshot), counted_qty(nullable until entered), variance_qty(nullable until entered). Each sheet snapshots every active stocked product in its warehouse, including zero-balance products; posting is rejected if stock or the stocked-product scope changed after the snapshot.

## 5. Purchase
**purchase_orders**: id, doc_no, doc_date, supplier_id(FK), warehouse_id(FK), status, expected_date, subtotal, discount, total, note
**purchase_order_lines**: id, po_id(FK), product_id, qty, unit_price, line_total, received_qty
**goods_receipts**: id, doc_no, doc_date, po_id(FK, null), supplier_id, warehouse_id, status, total, note
**goods_receipt_lines**: id, receipt_id(FK), po_line_id(FK, null), product_id, qty, unit_cost, line_total
**direct_purchases**: id, doc_no, doc_date, supplier_id, warehouse_id, status, total, paid_amount, money_account_id(null)
**direct_purchase_lines**: id, purchase_id(FK), product_id, qty, unit_cost, line_total
**purchase_returns**: id, doc_no, doc_date, supplier_id, receipt_id(FK), warehouse_id, status, total
**purchase_return_lines**: id, return_id(FK), receipt_line_id(FK), product_id, qty, unit_cost, line_total

## 6. Production
**boms**: id, code(U), finished_product_id(FK), output_qty, labor_cost_default, overhead_cost_default, is_active, deleted_at
**bom_lines**: id, bom_id(FK), raw_product_id(FK), qty; unique(bom_id, raw_product_id)
**production_orders**: id, doc_no(U), doc_date, bom_id(FK), sales_order_line_id(FK→sales_order_lines, null), finished_product_id(FK), planned_qty, actual_qty, warehouse_id(FK), status(DRAFT/IN_PROGRESS/COMPLETED/CANCELLED), labor_cost, overhead_cost, material_cost, total_cost, unit_cost(DECIMAL 18,4), created_by(FK), created_at, updated_at
**production_consumption**: id, production_order_id(FK), product_id(FK), qty, unit_cost(DECIMAL 18,4), line_cost
**production_outputs**: id, production_order_id(FK), product_id(FK), qty, unit_cost(DECIMAL 18,4)

BOMs require a stocked `FINISHED` product and unique stocked `RAW` material lines. Quantities use
three decimal places; default labor and overhead costs use two. Deletion is soft and audited.
Production orders use centrally numbered drafts. Starting checks material availability; completion
posts consumption and output through the inventory service and snapshots actual costs atomically.
The finished-good average cost is updated using the resulting production unit cost. An optional
Sales Order line link must match the finished good and warehouse; completion updates that line's
`qty_produced` in the same transaction and rejects quantities exceeding unreserved, undelivered
remaining demand.

## 7. Sales
**quotations**: id, doc_no, doc_date, customer_id(FK), valid_until, status(DRAFT/SENT/ACCEPTED/REJECTED), subtotal, discount, total, note, created_by(FK), created_at, updated_at
**quotation_lines**: id, quotation_id(FK), product_id, qty, unit_price, line_total
**sales_orders**: id, doc_no, doc_date, customer_id(FK), quotation_id(FK, null, unique), warehouse_id, status, delivery_date, subtotal, discount, total, note, created_by(FK), created_at, updated_at
**sales_order_lines**: id, order_id(FK), product_id, qty_ordered, unit_price, line_total, qty_reserved, qty_produced, qty_delivered
**deliveries**: id, doc_no, doc_date, order_id(FK), customer_id(FK), warehouse_id(FK), status(POSTED), created_by(FK), created_at
**delivery_lines**: id, delivery_id(FK), order_line_id(FK), product_id(FK), qty, unit_cost_cogs (weighted-average cost captured at posting)
**invoices**: id, doc_no, doc_date, due_date, customer_id(FK), delivery_id(FK, unique), status(POSTED), subtotal, discount, total, cogs_total, created_by(FK), created_at
**invoice_lines**: id, invoice_id(FK), product_id(FK), qty, unit_price, line_total, unit_cost_cogs
**sales_returns**: id, doc_no, doc_date, invoice_id(FK), customer_id(FK), warehouse_id(FK), status(POSTED), total, note, created_by(FK), created_at
**sales_return_lines**: id, return_id(FK), invoice_line_id(FK), product_id(FK), qty, unit_price, line_total, unit_cost_cogs

The Phase 4 reservation prerequisite migration creates only the `sales_orders` and
`sales_order_lines` columns needed for valid reservation references. Phase 7 adds quotation linkage
and completes the Sales Order document fields. Quotations transition from DRAFT to SENT, then to
ACCEPTED or REJECTED. Only ACCEPTED quotations can be converted; a unique `sales_orders.quotation_id`
allows at most one linked order.

Sales Order reserve/release actions reuse the Phase 4 `stock_reservations` service and balance
updates. Draft edits are rejected once any reservation history exists, including fully released
reservations. Delivery lines consume active reservations first and reserve/consume any remaining
available quantity through the same inventory service. Delivery and stock changes are atomic;
delivery status is `POSTED`, and partial deliveries do not change the Sales Order status.
Each posted delivery can have at most one posted invoice. Invoice lines snapshot the sales-order
unit price and delivery COGS; the invoice header stores the delivery's sales subtotal, its
proportional share of any Sales Order discount, and total COGS. The invoice increases customer due
in the statement calculation; the configured `credit_limit_mode` controls whether exceeding the
customer credit limit warns or blocks posting.
Sales returns reference the original posted invoice and line, cannot exceed the line's remaining
invoiced quantity, and restock through the inventory posting service at the stored COGS. Each return
line snapshots the original unit price, discounted refund amount, and original unit COGS. Posted
returns reduce customer due in the statement calculation.

## 8. Money
**money_transactions** (ledger, append-only): id, txn_date, account_id(FK), amount_signed, txn_type(COLLECTION/PAYMENT/EXPENSE/INCOME/TRANSFER_OUT/TRANSFER_IN/OPENING/PURCHASE_PAYMENT/SALARY), source_type, source_id, party_type, party_id, note, created_by, created_at. `money_accounts.opening_balance` is the pre-ledger baseline; `OPENING` transactions are later signed adjustments included in the sum, and the baseline is immutable after the first ledger transaction.
**customer_collections**: id, doc_no, doc_date, customer_id, account_id, amount, method_ref, status, note
**collection_allocations**: id, collection_id(FK), invoice_id(FK), amount
**supplier_payments**: id, doc_no, doc_date, supplier_id, account_id, amount, status, note
**payment_allocations**: id, payment_id(FK), ref_type(RECEIPT/DIRECT_PURCHASE), ref_id, amount
**expenses**: id, doc_no, doc_date, category_id(FK), account_id, amount, paid_to, status, note
**incomes**: id, doc_no, doc_date, category_id(FK), account_id, amount, status, note
**fund_transfers**: id, doc_no, doc_date, from_account_id, to_account_id, amount, status, note

## 9. Assets
**assets**: id, asset_code(U), name, category, purchase_date, purchase_cost(DECIMAL 18,2), location, status(IN_USE/IN_STORE/UNDER_MAINTENANCE/DISPOSED), is_active, deleted_at, created_by, created_at, updated_at
**asset_assignments**: id, asset_id(FK), employee_id(FK→employees, null), location, assigned_on, returned_on, created_at
**asset_maintenance**: id, asset_id(FK), maintenance_date, description, cost(DECIMAL 18,2), next_due_date, created_by, created_at

Assets use soft deletion. Assignment history records the location and optionally the assigned
employee; the linked employee must be active when the assignment is created.

## 10. Employees
**employees**: id, code(U), name, mobile(nullable for legacy rows; all writes require a valid 11-digit Bangladesh number), email(null), designation(null), department(null), join_date, base_salary(DECIMAL 18,2), is_active, deleted_at, created_at, updated_at
**attendance**: id, employee_id(FK), att_date, status(PRESENT/ABSENT/LEAVE/LATE), in_time, out_time, (U employee_id+att_date)
**payroll_runs**: id, doc_no(null until post), period_month, period_year, status(DRAFT/POSTED), total_amount, paid_on, account_id(FK→money_accounts), created_by(FK→users), created_at, (U period_month+period_year)
**payroll_lines**: id, run_id(FK), employee_id(FK), base_salary(snapshot), deductions, net_pay, paid_txn_id(FK→money_transactions, null)

The employee master uses `is_active` and `deleted_at` for status/soft deletion; it does not add a
second status field. `users.employee_id` is a nullable FK to `employees.id` and links a user account
to an active employee when provided. Employee references use restrictive foreign keys; employee
records are soft-deleted rather than hard-deleted.

Payroll snapshots eligible active employees' base salaries when a monthly draft is created.
Deductions are entered on the draft and cannot exceed base salary; the selected scope has no
allowances or overtime. Posting generates the central `PAYROLL` document number and, in one
transaction, writes one `SALARY` money-ledger row per employee with a nonzero net pay. Posted runs
are immutable.

Attendance records are unique per employee and date and retain status/time corrections in the
audit log. Excel imports identify employees by code, reject duplicate employee/date records, and
report invalid rows while allowing valid rows in the same workbook to be saved.

## 11. Approvals
**approval_rules**: id, doc_type, min_amount, max_amount(null), approver_role_id(FK), is_active
**approval_requests**: id, doc_type, doc_id, amount(DECIMAL 18,2; snapshot used for rule matching), requested_by, rule_id(FK), status(PENDING/APPROVED/REJECTED), requested_at, decided_at
**approval_actions**: id, request_id(FK), user_id, action(APPROVE/REJECT), note, acted_at

Approval rule ranges are inclusive and active ranges for the same document type cannot overlap.
Rule configuration is implemented; requests/actions and hooks into document posting workflows remain
pending.

---
## Views (read-only)
| View | Purpose |
|---|---|
| `v_current_stock` | product, warehouse, on-hand, reserved, available, avg_cost, value |
| `v_stock_valuation` | per product and total value (on-hand × avg_cost) |
| `v_customer_due` | opening + posted invoices − collections − returns, per customer |
| `v_supplier_due` | opening + receipts/direct purchases − payments − returns, per supplier |
| `v_account_balance` | opening + SUM(money_transactions) per account |
| `v_order_status` | ordered / reserved / produced / delivered / remaining per order line |
| `v_profit_summary` | sales − COGS − expenses by period |
| `v_dashboard_kpis` | the 11 dashboard KPIs for a date |
| `v_low_stock` | products at/below reorder level |

## Key constraints
- `CHECK (qty_on_hand >= 0)` on `stock_balances` (stocked products).
- `UNIQUE(doc_no)` on every document table.
- `CHECK (amount > 0)` on collections, payments, expenses, incomes, transfers.
- `CHECK (from_account_id <> to_account_id)` on `fund_transfers`.
- `CHECK (from_warehouse_id <> to_warehouse_id)` on `stock_transfers`.
- Stock and money ledgers: no UPDATE/DELETE (enforced in the service layer, plus DB permissions in production).

## Key indexes
`stock_transactions(product_id, warehouse_id, txn_date)`, `money_transactions(account_id, txn_date)`, `(source_type, source_id)` on both ledgers, `invoices(customer_id, status)`, `goods_receipts(supplier_id, status)`, `audit_logs(entity_type, entity_id)`.

## Invariants (must have tests)
1. `stock_balances.qty_on_hand = SUM(stock_transactions.qty_signed)` per product + warehouse.
2. Account balance = `opening_balance + SUM(money_transactions.amount_signed)`.
3. Customer due = opening + posted invoices − collections − returns.
4. Supplier due = opening + posted purchases − payments − returns.
5. Production `unit_cost × output_qty = material + labor + overhead`.
