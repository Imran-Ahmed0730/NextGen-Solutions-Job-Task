'use client';

import { useEffect, useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { useSessionProfile } from '@/components/auth/session-shell';
import { apiRequest } from '@/lib/auth-api';
import { showErrorToast } from '@/lib/notifications';

const REPORTS = [
  ['sales', 'Sales'],
  ['purchases', 'Purchases'],
  ['stock_valuation', 'Stock valuation'],
  ['low_stock', 'Low stock'],
  ['customer_due', 'Customer due'],
  ['supplier_due', 'Supplier due'],
  ['production_cost', 'Production cost'],
  ['cash_book', 'Cash book'],
  ['expense_income', 'Expenses and income'],
  ['profit', 'Profit summary'],
  ['assets', 'Asset register'],
  ['attendance_payroll', 'Attendance and payroll'],
] as const;

type ReportType = (typeof REPORTS)[number][0];
type ReportData = {
  report_type: ReportType;
  title: string;
  period_from: string;
  period_to: string;
  columns: string[];
  rows: Record<string, unknown>[];
};
type ReportOption = { id: number; label: string };
type ReportOptions = {
  customers: ReportOption[];
  suppliers: ReportOption[];
  products: ReportOption[];
  warehouses: ReportOption[];
};

const COLUMN_LABELS: Record<string, string> = {
  date: 'Date',
  document: 'Document',
  party: 'Party',
  type: 'Type',
  amount: 'Amount',
  cogs: 'COGS',
  sku: 'SKU',
  product: 'Product',
  on_hand: 'On hand',
  reorder_level: 'Reorder level',
  unit_cost: 'Unit cost',
  value: 'Value',
  code: 'Code',
  due: 'Due',
  status: 'Status',
  output_qty: 'Output quantity',
  material_cost: 'Material cost',
  labor_cost: 'Labor cost',
  overhead_cost: 'Overhead cost',
  total_cost: 'Total cost',
  account: 'Account',
  source: 'Source',
  source_id: 'Source ID',
  note: 'Note',
  sales: 'Sales',
  expenses: 'Expenses',
  estimated_profit: 'Estimated profit',
  asset_code: 'Asset code',
  asset: 'Asset',
  category: 'Category',
  purchase_date: 'Purchase date',
  purchase_cost: 'Purchase cost',
  location: 'Location',
  employee_count: 'Employee count',
  year: 'Year',
  month: 'Month',
  total_amount: 'Total amount',
};

const SNAPSHOT_REPORTS = new Set<ReportType>([
  'stock_valuation',
  'low_stock',
  'customer_due',
  'supplier_due',
  'assets',
]);

function dateString(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(
    date.getDate(),
  ).padStart(2, '0')}`;
}

function csvValue(value: unknown): string {
  const text = value == null ? '' : String(value);
  return `"${text.replaceAll('"', '""')}"`;
}

function ReportSkeleton() {
  return (
    <div aria-label="Loading report" role="status" className="animate-pulse p-5">
      <div className="mb-4 h-4 w-1/3 rounded bg-slate-200" />
      {Array.from({ length: 6 }, (_, row) => (
        <div key={row} className="grid grid-cols-4 gap-4 border-t border-slate-100 py-4">
          {Array.from({ length: 4 }, (_, column) => (
            <div
              key={column}
              className="h-4 rounded bg-slate-100"
              style={{ width: `${55 + ((row + column) % 4) * 10}%` }}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

function ReportsContent() {
  const canRead = useSessionProfile()?.permissions.includes('reports.read') ?? false;
  const today = dateString(new Date());
  const [reportType, setReportType] = useState<ReportType>('sales');
  const [periodFrom, setPeriodFrom] = useState(today);
  const [periodTo, setPeriodTo] = useState(today);
  const [options, setOptions] = useState<ReportOptions>({
    customers: [],
    suppliers: [],
    products: [],
    warehouses: [],
  });
  const [partyId, setPartyId] = useState('');
  const [productId, setProductId] = useState('');
  const [warehouseId, setWarehouseId] = useState('');
  const [data, setData] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const productDocumentFilter = ['sales', 'purchases'].includes(reportType) && Boolean(productId);

  async function loadReport(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    if (periodFrom > periodTo) {
      const message = 'Start date cannot be after end date.';
      setError(message);
      showErrorToast(message);
      return;
    }
    const params = new URLSearchParams({
      report_type: reportType,
      period_from: periodFrom,
      period_to: periodTo,
    });
    if (partyId && ['sales', 'customer_due'].includes(reportType)) {
      params.set('party_id', partyId);
    } else if (partyId && ['purchases', 'supplier_due'].includes(reportType)) {
      params.set('party_id', partyId);
    }
    if (productId && ['sales', 'purchases', 'stock_valuation', 'low_stock', 'production_cost'].includes(reportType)) {
      params.set('product_id', productId);
    }
    if (warehouseId && ['stock_valuation', 'low_stock', 'production_cost'].includes(reportType)) {
      params.set('warehouse_id', warehouseId);
    }
    setLoading(true);
    setError('');
    try {
      setData(await apiRequest<ReportData>(`/api/v1/reports?${params.toString()}`));
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not load report';
      setError(message);
      showErrorToast(message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (canRead) void loadReport();
    // Load once permissions are available; form submission handles later parameter changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canRead]);

  useEffect(() => {
    if (!canRead) return;
    let active = true;
    apiRequest<ReportOptions>('/api/v1/reports/options')
      .then((result) => {
        if (!active) return;
        setOptions({
          customers: result.customers ?? [],
          suppliers: result.suppliers ?? [],
          products: result.products ?? [],
          warehouses: result.warehouses ?? [],
        });
      })
      .catch((cause: unknown) => {
        if (!active) return;
        const message = cause instanceof Error ? cause.message : 'Could not load report filters';
        setError(message);
        showErrorToast(message);
      });
    return () => {
      active = false;
    };
  }, [canRead]);

  function downloadCsv() {
    if (!data) return;
    const content = [
      data.columns.map((column) => csvValue(COLUMN_LABELS[column] ?? column)).join(','),
      ...data.rows.map((row) => data.columns.map((column) => csvValue(row[column])).join(',')),
    ].join('\r\n');
    const blob = new Blob([`\uFEFF${content}`], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${data.report_type}-${data.period_from}-to-${data.period_to}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  if (!canRead) {
    return (
      <section className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
        Your account does not have permission to view business reports.
      </section>
    );
  }

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Report Center</h1>
        <p className="mt-1 text-sm text-slate-600">
          Choose a report and date range. Use CSV to download the displayed results or Print to save
          a PDF.
        </p>
      </header>
      <form
        onSubmit={(event) => void loadReport(event)}
        className="grid gap-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:grid-cols-2 xl:grid-cols-4"
      >
        <label className="text-sm font-medium text-slate-700">
          Report
          <select
            aria-label="Report"
            value={reportType}
            onChange={(event) => {
              setReportType(event.target.value as ReportType);
              setPartyId('');
              setProductId('');
              setWarehouseId('');
            }}
            className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2"
          >
            {REPORTS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        {['sales', 'customer_due', 'purchases', 'supplier_due'].includes(reportType) && (
          <label className="text-sm font-medium text-slate-700">
            {['sales', 'customer_due'].includes(reportType) ? 'Customer' : 'Supplier'}
            <select
              aria-label={['sales', 'customer_due'].includes(reportType) ? 'Customer' : 'Supplier'}
              value={partyId}
              onChange={(event) => setPartyId(event.target.value)}
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2"
            >
              <option value="">All parties</option>
              {(reportType === 'sales' || reportType === 'customer_due'
                ? options.customers
                : options.suppliers
              ).map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        )}
        {['sales', 'purchases', 'stock_valuation', 'low_stock', 'production_cost'].includes(
          reportType,
        ) && (
          <label className="text-sm font-medium text-slate-700">
            {['sales', 'purchases'].includes(reportType) ? 'Product in document' : 'Product'}
            <select
              aria-label="Product"
              value={productId}
              onChange={(event) => setProductId(event.target.value)}
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2"
            >
              <option value="">All products</option>
              {options.products.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        )}
        {['stock_valuation', 'low_stock', 'production_cost'].includes(reportType) && (
          <label className="text-sm font-medium text-slate-700">
            Warehouse
            <select
              aria-label="Warehouse"
              value={warehouseId}
              onChange={(event) => setWarehouseId(event.target.value)}
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2"
            >
              <option value="">All warehouses</option>
              {options.warehouses.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        )}
        <label className="text-sm font-medium text-slate-700">
          From date
          <input
            aria-label="From date"
            type="date"
            value={periodFrom}
            onChange={(event) => setPeriodFrom(event.target.value)}
            className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2"
          />
        </label>
        <label className="text-sm font-medium text-slate-700">
          To date
          <input
            aria-label="To date"
            type="date"
            value={periodTo}
            onChange={(event) => setPeriodTo(event.target.value)}
            className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2"
          />
        </label>
        <button
          type="submit"
          className="self-end rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-800"
        >
          View report
        </button>
      </form>
      {productDocumentFilter && (
        <p className="text-xs text-slate-500">
          Product filtering matches documents containing the selected product; displayed amounts
          are full document totals.
        </p>
      )}
      {error && (
        <p role="alert" className="rounded-md bg-rose-50 p-3 text-sm text-rose-800">
          {error}
        </p>
      )}
      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-4">
          <div>
            <h2 className="font-semibold text-slate-900">{data?.title ?? 'Report results'}</h2>
            {data && (
              <p className="mt-1 text-xs text-slate-500">
                {SNAPSHOT_REPORTS.has(data.report_type)
                  ? data.report_type === 'customer_due' || data.report_type === 'supplier_due'
                    ? `Balances as of ${data.period_to}`
                    : 'Current snapshot; selected dates do not filter these results'
                  : `${data.period_from} to ${data.period_to}`}
                {' · '}
                {data.rows.length} rows
              </p>
            )}
          </div>
          <div className="flex gap-2 print:hidden">
            <button
              type="button"
              onClick={downloadCsv}
              disabled={!data}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium disabled:opacity-50"
            >
              Export CSV
            </button>
            <button
              type="button"
              onClick={() => window.print()}
              disabled={!data}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium disabled:opacity-50"
            >
              Print / PDF
            </button>
          </div>
        </div>
        {loading ? (
          <ReportSkeleton />
        ) : !data ? (
          <p className="p-5 text-sm text-slate-600">Choose a report to view its results.</p>
        ) : data.rows.length === 0 ? (
          <p className="p-5 text-sm text-slate-600">No rows match the selected report and dates.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  {data.columns.map((column) => (
                    <th key={column} className="whitespace-nowrap px-4 py-3">
                      {COLUMN_LABELS[column] ?? column.replaceAll('_', ' ')}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.rows.map((row, index) => (
                  <tr key={`${String(row.document ?? row.date ?? row.code ?? 'row')}-${index}`}>
                    {data.columns.map((column) => (
                      <td key={column} className="whitespace-nowrap px-4 py-3">
                        {row[column] == null ? '—' : String(row[column])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </section>
  );
}

export default function ReportsPage() {
  return (
    <ProtectedPage>
      <ReportsContent />
    </ProtectedPage>
  );
}
