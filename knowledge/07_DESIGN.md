# DESIGN GUIDE (UI/UX)

Goal: a fast, clear, data-entry-friendly business UI. Consistency over decoration: every module uses the same patterns.

## 1. Principles
1. Clarity first: numbers, statuses and actions must be obvious.
2. Same pattern everywhere: List → Create/Edit → Details.
3. Keyboard-friendly data entry (tab order, Enter to submit, autofocus).
4. Show state: status badges, loading skeletons, empty states, clear errors.
5. Permission-aware: hide or disable what the user cannot do.
6. Desktop first; usable on tablet.

## 2. Layout
- **Sidebar** (collapsible) grouped by module; items filtered by permission.
- **Top bar:** breadcrumb, global search (documents/parties/products), notifications (pending approvals), user menu.
- **Content:** page title + primary action on the right, filter bar, data table or form.

## 3. Visual style
- Tailwind + shadcn/ui; neutral gray base, one brand color (primary), semantic colors for status.
- Light theme default; dark mode optional later.
- Font: Inter (or system UI). Numbers use tabular figures and are right-aligned.
- Spacing scale: 4/8/12/16/24. Radius: medium. Subtle borders instead of heavy shadows.

### Status colors
| Status | Color |
|---|---|
| Draft | Gray |
| Pending approval | Amber |
| Approved / Posted / Paid | Green |
| Partially received/paid | Blue |
| Cancelled / Rejected | Red |
| Overdue | Red outline |

## 4. Reusable components (build once)
`DataTable` (server pagination, sort, filters, column toggle, export), `FilterBar`, `PageHeader`, `StatusBadge`, `MoneyCell`, `QtyCell`, `FormSection`, `LineItemsGrid` (editable lines for PO/SO/etc.), `LookupSelect` (searchable select for products/customers/suppliers), `ConfirmDialog`, `DocumentTimeline` (status history), `ApprovalBanner`, `EmptyState`, `KpiCard`, `ChartCard`, `PrintLayout`.

## 5. Screen patterns
### List screen
Title, "New" button, filter bar (search, date range, status, party), table with row actions (View, Edit, Post/Cancel by status), pagination, export.

### Create/Edit form
Header fields in sections, `LineItemsGrid` for lines with live totals, sticky footer: *Save Draft*, *Submit/Post*, *Cancel*. Posted documents open read-only.

### Details screen
Header summary, status badge, tabs (Lines, Payments/Receipts, Stock effects, History/Audit), action buttons by status, print button.

## 6. Dashboard layout (Owner/Management)
- Row 1 KPI cards: Today's Sales, Collection, Expenses, Purchase.
- Row 2 KPI cards: Cash, Bank, MFS, Inventory Value.
- Row 3 KPI cards: Customer Due, Supplier Due, Pending Orders, Estimated Profit.
- Row 4 charts: Sales vs Collection (last 30 days), Expenses by category, Top products.
- Row 5 lists: Pending approvals, Low stock, Overdue customers.
Date range selector affects all widgets.

## 7. Forms & validation
- React Hook Form + Zod; errors inline under fields and a summary on submit failure.
- Backend error codes mapped to friendly messages (e.g. `STOCK_INSUFFICIENT` → "Only 12 KG available in Main Warehouse").
- Destructive/posting actions require a confirm dialog.

## 8. Print & documents
Print-optimized layouts for Invoice, Delivery challan, PO, Quotation, Customer/Supplier Statement: company header from settings, document number, party, lines, totals, signature area. A4, black and white friendly.

## 9. Accessibility & i18n
Labels linked to inputs, focus rings, color never the only status indicator (icon/text too). All UI text in a translation file (English first, Bangla-ready). Dates `DD/MM/YYYY`, currency BDT with thousand separators.
