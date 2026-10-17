# Full-Cycle Demo Script

This walkthrough uses the development/demo environment and demonstrates the complete business
cycle from supplier purchasing through dashboard reporting. It is not a production deployment
procedure. The optional runner is `scripts/demo.ps1`; it starts the development stack, initializes
demo data, runs the isolated full-cycle API test, and checks API health.

## Before the presentation

1. From the repository root, configure `.env` with a valid private `SECRET_KEY` and local database
   credentials. Do not use production data or credentials for this demo.
2. Run:

   ```powershell
   .\scripts\demo.ps1
   ```

3. If the admin account is being created for the first time, the seed prints its one-time password
   in the terminal. Record it securely. If `admin` already exists, the seed does not reset or
   display its password.
4. Sign in at <http://localhost:3000/login>. The reusable demo master records include:
   - Warehouse: **Demo Warehouse**
   - Supplier: **Demo Raw Materials Supplier** (`DEMO-SUP`)
   - Customer: **Demo Customer** (`DEMO-CUS`)
   - Raw material: **Demo Raw Material** (`DEMO-RAW-001`)
   - Finished product: **Demo Finished Product** (`DEMO-FG-001`)
   - Bill of Materials: **DEMO-BOM-001** (2 raw-material units per finished unit)
   - Accounts: **Demo Cash**, **Demo Bank**, **Demo MFS**
   - Expense category: **Demo Operating Expense**

The master-data seed is idempotent and creates document sequences for the current year. It does
not post transactions. For a repeatable, clean business-cycle example, the runner also executes
`backend/tests/test_full_cycle.py` against its isolated in-memory SQLite database; its assertions
verify the exact ledger and dashboard results without adding those test transactions to the
demo MySQL database.

## Guided application walkthrough

Perform the following in the UI. Exact buttons and document statuses are shown on the respective
screens; document numbers are allocated by the system.

### 1. Review the starting state

- Open **Products** and confirm the raw and finished demo products exist.
- Open **Bills of Materials** and inspect `DEMO-BOM-001`.
- Open **Money Accounts** and confirm the three demo accounts.
- Open **Dashboard** and note the initial values.

### 2. Purchase raw material from the supplier

- Create a purchase order for **Demo Raw Materials Supplier** in **Demo Warehouse**.
- Add **Demo Raw Material**, quantity 20, unit price 4.
- Submit the order. With no matching approval rule, it becomes approved; if approvals are
  configured, have an eligible different approver decide it.
- Create and post a goods receipt for all 20 units at unit cost 4.
- Review warehouse stock and the product stock ledger. Receipt posting adds stock, updates weighted
  average cost, and raises supplier due atomically.
- Create a standalone production order for **Demo Finished Product**, planned quantity 2, using
  **DEMO-BOM-001**. Start and complete it with actual output 2, labor cost 2, and overhead cost 2.
  This creates the initial two finished units at unit cost 10 for the reservation demonstration.

### 3. Create a sales order and fulfill it through production

- Create a sales order for **Demo Customer** with **Demo Finished Product**, quantity 5, unit price
  20.
- Reserve 2 finished units. Review the order's ordered, available, reserved, produced, delivered,
  and remaining quantities.
- Create a production order linked to the sales-order line using **DEMO-BOM-001**, planned quantity
  3, and **Demo Warehouse**.
- Start and complete it with actual output 3, labor cost 3, and overhead cost 3.
- Review the production order: material cost is 24, total cost is 30, and unit cost is 10.
- Deliver all 5 ordered units. The delivery consumes the existing reservation and the remaining
  available finished stock, and stores delivery-time COGS on the delivery line.

### 4. Invoice, collect, return, pay, and record an expense

- Create and post an invoice from the delivery; the demo order totals 100 with COGS 50 before
  returns.
- Record a customer collection of 40 into **Demo Cash**.
- Create a sales return for 1 invoiced unit. It restocks at the original delivery COGS and reduces
  customer due by 20.
- Create a purchase return for 1 received raw-material unit. It reduces stock and supplier due by
  the original receipt cost of 4.
- Record a supplier payment of 20 from **Demo Bank**.
- Record an expense of 10 in **Demo Operating Expense** paid from **Demo MFS**. If an approval rule
  matches, have an eligible different approver approve it before posting.

### 5. Reconcile the results

Open customer and supplier statements, stock ledger, cash book, and dashboard. For the isolated
automated full-cycle test, the verified expected values are:

| Measure | Expected |
| --- | ---: |
| Sales after sales return | 80.00 |
| Purchases after purchase return | 76.00 |
| Customer collection | 40.00 |
| Expense | 10.00 |
| Customer due | 40.00 |
| Supplier due | 56.00 |
| Cash account balance | 140.00 |
| Bank account balance | 30.00 |
| MFS account balance | 15.00 |
| Inventory value | 62.00 |
| Pending orders | 0 |
| Estimated profit | 30.00 |

The UI environment may already contain transactions, so its totals can exceed these isolated-test
figures. Compare the changes from the starting values and verify that the relevant statements and
ledger reports agree with the dashboard.

## Automated business-cycle check

The runner executes this test independently of the seeded demo MySQL records:

```powershell
Set-Location backend
python -m pytest -q tests/test_full_cycle.py
```

The test creates isolated test data and exercises purchase/receipt, reservation, production,
delivery/COGS, invoice, collection, purchase and sales returns, supplier payment, expense,
statements, money and stock invariants, and dashboard totals.
