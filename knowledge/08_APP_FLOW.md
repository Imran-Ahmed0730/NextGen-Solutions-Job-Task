# APP FLOW

## 1. Navigation map (sidebar → screens, ~71)

| Group | Screens |
|---|---|
| **Auth** | Login · Forgot Password · My Profile · Change Password |
| **Dashboard** | Owner / Management Dashboard |
| **Master Data** | Product List · Product Add/Edit · Categories · Units · Price List · Warehouses · Expense Categories · Income Categories · Payment Methods · Money Accounts · Company Settings |
| **Customers** | Searchable/Paginated Customer List · Customer Add/Edit · Contact Management · Customer Statement |
| **Suppliers** | Searchable/Paginated Supplier List · Supplier Add/Edit · Contact Management · Supplier Statement |
| **Purchase** | PO List · Create/Edit PO · PO Details · Goods Receive · Direct Purchase · Purchase Return |
| **Inventory** | Current Stock · Product Stock Ledger · Stock Transfer · Stock Adjustment · Physical Count |
| **Production** | BOM List · BOM Create/Edit · Production Order List · Create/Edit Production Order · Production Details & Costing |
| **Sales** | Quotation List · Create/Edit Quotation · Sales Order List · Create/Edit Sales Order · Sales Order Details · Delivery · Invoice List · Invoice Details/Print · Sales Return |
| **Money** | Account Balances · Customer Collection · Supplier Payment · Expense Entry · Income Entry · Fund Transfer · Opening Balances · Account Ledger / Cash Book |
| **Assets** | Asset List · Asset Add/Edit · Asset Assignment & Maintenance |
| **Employees** | Employee List · Employee Add/Edit · Attendance · Basic Payroll |
| **Administration** | User List · User Add/Edit · Roles · Permissions · Approval Rules · Pending Approvals · Audit Log · Document Numbering / System Config |
| **Reports** | Report Center · Report Viewer |

Sidebar items are shown only if the user has the required `module.resource.action` permission.

## 2. Authentication flow
```
Open app → no valid token? → Login
Login (username/email/mobile + password)
  ├─ success → store tokens → Dashboard (or role landing page)
  ├─ failure → inline error; lock for 15 minutes after 5 failed attempts
  └─ Forgot Password → enter registered email → receive one-time reset link → set new password → Login
Token expired → silent refresh → if refresh fails → Login
Change Password (from profile) → verify old → set new → keep session
Sign out (requires `auth.session.logout`) → revoke current session → Login
```

## 3. Standard document lifecycle
```
DRAFT ──submit──▶ (rule matches?) ─yes─▶ PENDING_APPROVAL ─approve─▶ APPROVED
   │                   └─no──────────────────────────────────────────▶ APPROVED
   │                                                         reject ─▶ REJECTED (→ edit → DRAFT)
   └──cancel──▶ CANCELLED
APPROVED ──post──▶ POSTED (immutable; stock/money/due effects written in one transaction)
POSTED ──return/reversal/adjustment──▶ new document (never edit the original)
```

## 4. Master business cycle
This is the target business workflow. For implementation sequencing, Phase 7 Sales initially
fulfills orders from available/reserved stock; Production-backed shortage fulfillment is added in
the supplemental Phase 8 described in `05_PLAN.md`.

```
Supplier ─▶ Purchase Order ─▶ Goods Receive ─▶ [Stock ↑, Avg Cost, Supplier Due ↑]
                                   │
                                   ▼
Sales Quotation ─▶ Sales Order ─▶ Reserve stock ─▶ enough? ──no──▶ Production Order
                                   │                                  │ consume raw, output FG, cost
                                   ▼ yes                              ▼
                               Delivery ◀─────────────────────────────┘
                     [Stock ↓, COGS recorded] ─▶ Invoice [Customer Due ↑]
                                   │
                                   ▼
                      Customer Collection ─▶ [Customer Due ↓, Cash/Bank/MFS ↑]
                                   │
Supplier Payment [Supplier Due ↓, account ↓] · Expense [account ↓] · Income [account ↑]
                                   ▼
                       Management Dashboard + Reports
```

## 5. Module flows

### 5.0 Customers and suppliers (Phase 3)
1. Create and maintain the party master, primary contact details, opening due, and (for customers)
   credit limit and optional price list.
2. Maintain additional named contacts from the Contacts action on the party list.
3. Open the party statement to review its opening-balance entry and current opening balance.
4. Search and page through party records; permissions are checked by the API for every operation.
5. Posted purchases, purchase returns, customer collections, and supplier payments are included in
   the applicable party statement. Posted sales invoices and sales returns are included in customer
   statements.

### 5.1 Purchase
1. Create PO (supplier, warehouse, lines) → Save Draft → Submit.
2. Approval rule check → Approved.
3. Goods Receive against PO (partial allowed) → Post → stock ledger rows, average cost update, supplier due raised, PO status `PARTIALLY_RECEIVED/RECEIVED`.
4. Direct Purchase: same effects without PO (and optional immediate payment).
5. Purchase Return: pick receipt, qty ≤ received → Post → stock ↓, supplier due ↓.
6. Supplier Payment from Money module reduces due.

### 5.2 Inventory
- **Transfer:** from-warehouse → to-warehouse, lines → Post → `TRANSFER_OUT` + `TRANSFER_IN` atomically.
- **Adjustment:** reason + lines (+/−) → (approval if configured) → Post → `ADJUSTMENT_IN/OUT`.
- **Physical Count:** start count sheet (snapshot of active stocked products, including zero balances) → enter counted qty → review variances → Post → `COUNT_ADJUSTMENT` rows. Posting is rejected if stock or the stocked-product scope changed after the snapshot; start a fresh count before posting.
- **Stock Ledger:** product + warehouse + date filters → every movement with running balance and source document link.

### 5.3 Production
1. Maintain a BOM with a stocked finished good, output quantity, raw-material quantities, and
   default labor/overhead costs. BOM List and Create/Edit are available at `/boms`.
2. Create a draft Production Order from an active BOM, planned output quantity, and warehouse.
3. Start → check raw material availability; a shortage blocks the transition.
4. Complete → enter actual output quantity and labor/overhead costs. One transaction consumes raw
   materials (`PRODUCTION_CONSUME`), adds finished goods (`PRODUCTION_OUTPUT`), snapshots
   consumption/output costs, updates weighted-average cost, and audits the completion.
5. Production-order-to-sales-order shortage linking and the Sales Order *Produced* quantity update
   remain to be implemented.

### 5.4 Sales
1. Quotation draft → Send → customer response → Accept or Reject. Only Accepted quotations can be
   converted, and each can create one linked Sales Order; direct Sales Order creation remains
   available.
2. Sales Order → Reserve: reserves available stock through the Phase 4 reservation service; a draft
   order cannot be edited after reservation history exists. Shortage can raise a Production Order.
3. Order Details shows Ordered / Available / Reserved / Produced / Delivered / Remaining.
4. Delivery (partial allowed) → Post → stock ↓, COGS stored per line, reservation released.
5. Invoice from delivery → Post once per delivery → customer due ↑; credit-limit mode warns or blocks.
6. Sales Return → qty ≤ delivered → Post → stock ↑ at original COGS, customer due ↓ (or credit note).

Quotation statuses follow `DRAFT → SENT → ACCEPTED` or `REJECTED`. Only DRAFT quotations can be
edited; SENT quotations can be accepted or rejected. Conversion copies the accepted quotation's
customer, product quantities, prices, discount, and note into a new Sales Order and requires an
order date and warehouse. A unique Sales Order quotation reference enforces one-time conversion.

Current delivery includes quotation lifecycle and conversion, and draft Sales Order
create/edit/list/detail workflows.
Order details show ordered quantity, current available warehouse stock (on-hand minus reserved),
reserved quantity, produced quantity, delivered quantity, and remaining quantity (ordered minus
delivered). Sales Order reservation, release, and delivery posting call the Phase 4 inventory reservation and
stock-posting service. Deliveries consume reservations first, reserve-and-consume any remaining
available quantity in the same transaction, and store the transaction's unit cost as line-level COGS.
Partial deliveries leave the Sales Order status unchanged; delivered quantities and delivery history
show progress. A posted delivery can be invoiced once. Invoices snapshot delivered quantities,
order prices, and delivery COGS; posting updates the customer statement and checks the configured
credit-limit mode. Sales Returns reference invoice lines and cap returns at remaining invoiced
quantity. Posting creates an immutable document, restores stock at the invoice line's stored COGS,
and reduces customer due using the invoice's discount-adjusted value. Order tracking is included in
Sales Order details.

### 5.5 Money
- **Customer Collection:** customer, account, amount, optional reference → Post → customer due ↓,
  account ↑. Customer collections are party-level until invoices are implemented in Phase 7.
- **Supplier Payment:** supplier, account, amount, optional allocation to outstanding Goods Receipts
  or Direct Purchases → Post → supplier due ↓, account ↓. Any unallocated amount remains against
  the supplier balance.
- **Expense / Income:** category, account, amount (approval if over threshold) → Post → account ↓/↑.
- **Fund Transfer:** from account → to account → two linked ledger rows.
- **Opening Balances:** one-time per account/party at go-live.

### 5.5b Employees
Employee master → daily/monthly Attendance → Payroll run (salary, deductions) → Approve → Pay via Money (account ↓, expense recorded) → payslip.

### 5.6 Assets
Register asset → assign to employee/location → log maintenance → view history.

### 5.7 Approvals
```
Document submitted → engine finds rule (type + amount) → creates approval request
→ approver role sees it in Pending Approvals → Approve / Reject (with note)
→ approved: document becomes APPROVED and can be posted
→ rejected: back to requester with reason
Requester ≠ approver. All actions audit-logged.
```

### 5.8 Reports & Dashboard
Report Center (grouped list) → choose report → Report Viewer (parameters, table, totals, chart where useful) → Print / PDF / CSV. Dashboard KPIs read from database views; clicking a KPI opens the matching report.

## 6. Error and edge flows
| Situation | Behavior |
|---|---|
| Insufficient stock | Block post; show product, warehouse, available qty |
| Over-receiving / over-delivering | Block beyond tolerance |
| Editing posted document | Not allowed; offer Return/Reversal |
| Permission missing | Hide action; API returns 403 with `PERMISSION_DENIED` |
| Concurrent edit | Version check; ask user to reload |
| Posting failure | Whole transaction rolled back; user sees reason; nothing partially saved |
