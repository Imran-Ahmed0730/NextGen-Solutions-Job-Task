'use client';

import { useCallback, useEffect, useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { useSessionProfile } from '@/components/auth/session-shell';
import { RequiredMark } from '@/components/forms/field-error';
import { SearchableSelect } from '@/components/forms/searchable-select';
import { apiRequest } from '@/lib/auth-api';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';
import { salesReturnSchema } from '@/lib/auth-validation';

type InvoiceLineOption = {
  invoice_line_id: number;
  product_id: number;
  product_sku: string;
  product_name: string;
  unit_code: string;
  allow_decimal: boolean;
  qty_invoiced: string;
  qty_returned: string;
  qty_available: string;
  unit_price: string;
  unit_cost_cogs: string;
};
type InvoiceOption = {
  id: number;
  doc_no: string;
  doc_date: string;
  lines: InvoiceLineOption[];
};
type SalesReturnOptions = { invoices: InvoiceOption[] };
type DraftLine = { invoice_line_id: number; qty: string };
type SalesReturnLine = {
  id: number;
  invoice_line_id: number;
  product_id: number;
  product_sku: string;
  product_name: string;
  qty: string;
  unit_code: string;
  unit_price: string;
  line_total: string;
  unit_cost_cogs: string;
};
type SalesReturn = {
  id: number;
  doc_no: string;
  doc_date: string;
  invoice_id: number;
  invoice_doc_no: string;
  customer_id: number;
  warehouse_id: number;
  status: string;
  total: string;
  note: string | null;
  lines: SalesReturnLine[];
};

const PAGE_SIZE = 50;

function today(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(
    now.getDate(),
  ).padStart(2, '0')}`;
}

function SalesReturnsContent() {
  const profile = useSessionProfile();
  const canRead = profile?.permissions.includes('sales.returns.read') ?? false;
  const canCreate = profile?.permissions.includes('sales.returns.create') ?? false;
  const [options, setOptions] = useState<SalesReturnOptions>({ invoices: [] });
  const [returns, setReturns] = useState<SalesReturn[]>([]);
  const [selectedInvoiceId, setSelectedInvoiceId] = useState('');
  const [docDate, setDocDate] = useState(today);
  const [note, setNote] = useState('');
  const [lines, setLines] = useState<DraftLine[]>([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const reload = useCallback(async (nextOffset = 0) => {
    const [loadedOptions, loadedReturns] = await Promise.all([
      apiRequest<SalesReturnOptions>('/api/v1/sales/returns/options'),
      apiRequest<SalesReturn[]>(
        `/api/v1/sales/returns?offset=${nextOffset}&limit=${PAGE_SIZE + 1}`,
      ),
    ]);
    setOptions(loadedOptions);
    setReturns(loadedReturns.slice(0, PAGE_SIZE));
    setHasMore(loadedReturns.length > PAGE_SIZE);
    setOffset(nextOffset);
  }, []);

  useEffect(() => {
    if (!canRead) return;
    let active = true;
    setLoading(true);
    reload()
      .catch((cause: unknown) => {
        if (!active) return;
        const message = cause instanceof Error ? cause.message : 'Could not load sales returns';
        setError(message);
        showErrorToast(message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [canRead, reload]);

  function chooseInvoice(value: string) {
    setSelectedInvoiceId(value);
    setError('');
    const invoice = options.invoices.find((candidate) => String(candidate.id) === value);
    setLines(
      invoice
        ? invoice.lines.map((line) => ({ invoice_line_id: line.invoice_line_id, qty: '' }))
        : [],
    );
  }

  function updateLine(index: number, value: string) {
    setLines((current) =>
      current.map((line, lineIndex) => (lineIndex === index ? { ...line, qty: value } : line)),
    );
  }

  function resetForm() {
    setSelectedInvoiceId('');
    setDocDate(today());
    setNote('');
    setLines([]);
    setError('');
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = salesReturnSchema.safeParse({
      doc_date: docDate,
      invoice_id: Number(selectedInvoiceId),
      note,
      lines: lines
        .filter((line) => line.qty.trim() !== '')
        .map((line) => ({ invoice_line_id: line.invoice_line_id, qty: line.qty })),
    });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? 'Check the sales return details.');
      return;
    }

    setError('');
    setSaving(true);
    try {
      const posted = await apiRequest<SalesReturn>('/api/v1/sales/returns', {
        method: 'POST',
        body: JSON.stringify(parsed.data),
      });
      showSuccessToast(`Sales return ${posted.doc_no} posted.`);
      resetForm();
      try {
        await reload(0);
      } catch (cause) {
        const message =
          cause instanceof Error
            ? `Return posted, but the history could not be refreshed: ${cause.message}`
            : 'Return posted, but the history could not be refreshed.';
        setError(message);
        showErrorToast(message);
      }
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not post sales return';
      setError(message);
      showErrorToast(message);
    } finally {
      setSaving(false);
    }
  }

  async function changePage(nextOffset: number) {
    setLoading(true);
    setError('');
    try {
      await reload(nextOffset);
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not load sales returns';
      setError(message);
      showErrorToast(message);
    } finally {
      setLoading(false);
    }
  }

  if (!canRead) {
    return (
      <section className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
        Your account does not have permission to view sales returns.
      </section>
    );
  }

  const selectedInvoice = options.invoices.find(
    (invoice) => String(invoice.id) === selectedInvoiceId,
  );

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Sales Returns</h1>
        <p className="mt-1 text-sm text-slate-600">
          Return invoiced quantities only. Returned items restock at their original COGS, and the
          invoice discount is reflected in the customer due reduction.
        </p>
      </header>

      {canCreate && (
        <form
          onSubmit={(event) => void submit(event)}
          className="space-y-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
        >
          <h2 className="text-lg font-semibold text-slate-900">Post sales return</h2>
          {options.invoices.length === 0 ? (
            <p className="rounded-md bg-amber-50 p-3 text-sm text-amber-900">
              No invoice lines have quantities remaining to return.
            </p>
          ) : (
            <>
              <div className="grid gap-4 md:grid-cols-2">
                <label className="text-sm font-medium text-slate-700">
                  Invoice<RequiredMark />
                  <SearchableSelect
                    aria-label="Invoice"
                    required
                    placeholder="Search invoice by number"
                    value={selectedInvoiceId}
                    onChange={chooseInvoice}
                    options={options.invoices.map((invoice) => ({
                      value: String(invoice.id),
                      label: `${invoice.doc_no} (${invoice.doc_date})`,
                      searchText: `${invoice.doc_no} ${invoice.doc_date}`,
                    }))}
                    className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
                  />
                </label>
                <label className="text-sm font-medium text-slate-700">
                  Return date<RequiredMark />
                  <input
                    aria-label="Return date"
                    type="date"
                    required
                    value={docDate}
                    onChange={(event) => setDocDate(event.target.value)}
                    className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
                  />
                </label>
                <label className="text-sm font-medium text-slate-700 md:col-span-2">
                  Note
                  <input type="text"
                    aria-label="Return note"
                    maxLength={2000}
                    value={note}
                    onChange={(event) => setNote(event.target.value)}
                    placeholder="Optional return note"
                    className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
                  />
                </label>
              </div>

              {selectedInvoice && (
                <div className="rounded-md bg-slate-50 p-3 text-sm text-slate-700">
                  Invoice {selectedInvoice.doc_no} dated {selectedInvoice.doc_date}
                </div>
              )}

              {lines.map((line, index) => {
                const sourceLine = selectedInvoice?.lines.find(
                  (candidate) => candidate.invoice_line_id === line.invoice_line_id,
                );
                if (!sourceLine) return null;
                return (
                  <div
                    key={line.invoice_line_id}
                    className="grid gap-3 rounded-lg border border-slate-200 p-3 md:grid-cols-[2fr_1fr_1fr]"
                  >
                    <div className="text-sm text-slate-700">
                      <p className="font-medium text-slate-900">
                        {sourceLine.product_sku} — {sourceLine.product_name}
                      </p>
                      <p className="mt-1">
                        Invoiced {sourceLine.qty_invoiced}; returned {sourceLine.qty_returned};
                        returnable {sourceLine.qty_available} {sourceLine.unit_code}
                      </p>
                      <p className="mt-1">
                        Original price {sourceLine.unit_price} · COGS{' '}
                        {sourceLine.unit_cost_cogs}
                      </p>
                    </div>
                    <label className="text-sm font-medium text-slate-700">
                      Return quantity ({sourceLine.unit_code})
                      <input
                        aria-label={`Return quantity ${index + 1}`}
                        type="number"
                        min="0"
                        max={sourceLine.qty_available}
                        step={sourceLine.allow_decimal ? '0.001' : '1'}
                        value={line.qty}
                        onChange={(event) => updateLine(index, event.target.value)}
                        placeholder="Enter return quantity"
                        className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
                      />
                    </label>
                    <p className="self-center text-sm text-slate-600">
                      The return reduces customer due at the invoice&apos;s discounted value.
                    </p>
                  </div>
                );
              })}

              {error && (
                <p role="alert" className="rounded-md bg-rose-50 p-3 text-sm text-rose-800">
                  {error}
                </p>
              )}
              <button
                type="submit"
                disabled={saving || !selectedInvoice || lines.length === 0}
                className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-800 disabled:opacity-60"
              >
                {saving ? 'Posting…' : 'Post return'}
              </button>
            </>
          )}
          {error && options.invoices.length === 0 && (
            <p role="alert" className="rounded-md bg-rose-50 p-3 text-sm text-rose-800">
              {error}
            </p>
          )}
        </form>
      )}

      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 px-5 py-4">
          <h2 className="font-semibold text-slate-900">Sales return history</h2>
        </div>
        {loading ? (
          <p className="p-5 text-sm text-slate-600">Loading sales returns…</p>
        ) : returns.length === 0 ? (
          <p className="p-5 text-sm text-slate-600">No sales returns found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-600">
                <tr>
                  <th className="px-4 py-3">Return</th>
                  <th className="px-4 py-3">Date</th>
                  <th className="px-4 py-3">Invoice</th>
                  <th className="px-4 py-3 text-right">Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {returns.map((salesReturn) => (
                  <tr key={salesReturn.id}>
                    <td className="px-4 py-3 font-medium text-slate-900">{salesReturn.doc_no}</td>
                    <td className="px-4 py-3">{salesReturn.doc_date}</td>
                    <td className="px-4 py-3">{salesReturn.invoice_doc_no}</td>
                    <td className="px-4 py-3 text-right">{salesReturn.total}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {!loading && returns.length > 0 && (
          <div className="flex items-center justify-between border-t border-slate-200 px-5 py-3">
            <button
              type="button"
              disabled={offset === 0}
              onClick={() => void changePage(Math.max(0, offset - PAGE_SIZE))}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-50"
            >
              Previous
            </button>
            <span className="text-sm text-slate-600">
              Page {Math.floor(offset / PAGE_SIZE) + 1}
            </span>
            <button
              type="button"
              disabled={!hasMore}
              onClick={() => void changePage(offset + PAGE_SIZE)}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-50"
            >
              Next
            </button>
          </div>
        )}
      </section>
    </section>
  );
}

export default function SalesReturnsPage() {
  return (
    <ProtectedPage>
      <SalesReturnsContent />
    </ProtectedPage>
  );
}
