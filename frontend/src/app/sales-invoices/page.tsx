'use client';

import { useCallback, useEffect, useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { useSessionProfile } from '@/components/auth/session-shell';
import { FieldError, RequiredMark } from '@/components/forms/field-error';
import { SearchableSelect } from '@/components/forms/searchable-select';
import { apiRequest } from '@/lib/auth-api';
import { salesInvoiceSchema } from '@/lib/auth-validation';
import { showErrorToast, showSuccessToast, showToast } from '@/lib/notifications';

type DeliveryOption = {
  id: number;
  doc_no: string;
  doc_date: string;
  order_doc_no: string;
};
type SalesInvoiceLine = {
  id: number;
  product_id: number;
  qty: string;
  unit_price: string;
  line_total: string;
  unit_cost_cogs: string;
};
type SalesInvoice = {
  id: number;
  doc_no: string;
  doc_date: string;
  due_date: string;
  customer_id: number;
  delivery_id: number;
  status: string;
  subtotal: string;
  discount: string;
  total: string;
  cogs_total: string;
  lines: SalesInvoiceLine[];
};
type InvoiceCreateResult = { invoice: SalesInvoice; credit_limit_warning: boolean };
type InvoiceOptions = { deliveries: DeliveryOption[] };

function today(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(
    now.getDate(),
  ).padStart(2, '0')}`;
}

function SalesInvoicesContent() {
  const profile = useSessionProfile();
  const canRead = profile?.permissions.includes('sales.invoices.read') ?? false;
  const canCreate = profile?.permissions.includes('sales.invoices.create') ?? false;
  const [options, setOptions] = useState<InvoiceOptions>({ deliveries: [] });
  const [invoices, setInvoices] = useState<SalesInvoice[]>([]);
  const [deliveryId, setDeliveryId] = useState('');
  const [docDate, setDocDate] = useState(today);
  const [dueDate, setDueDate] = useState(today);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const reload = useCallback(async () => {
    const [loadedOptions, loadedInvoices] = await Promise.all([
      apiRequest<InvoiceOptions>('/api/v1/sales/invoices/options'),
      apiRequest<SalesInvoice[]>('/api/v1/sales/invoices?limit=50'),
    ]);
    setOptions(loadedOptions);
    setInvoices(loadedInvoices);
  }, []);

  useEffect(() => {
    if (!canRead) return;
    let active = true;
    setLoading(true);
    reload()
      .catch((cause: unknown) => {
        if (!active) return;
        const message = cause instanceof Error ? cause.message : 'Could not load sales invoices';
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

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = salesInvoiceSchema.safeParse({
      delivery_id: Number(deliveryId),
      doc_date: docDate,
      due_date: dueDate,
    });
    if (!parsed.success) {
      const message = parsed.error.issues[0]?.message ?? 'Check the invoice details.';
      setError(message);
      return;
    }

    setSaving(true);
    setError('');
    try {
      const result = await apiRequest<InvoiceCreateResult>('/api/v1/sales/invoices', {
        method: 'POST',
        body: JSON.stringify(parsed.data),
      });
      showSuccessToast(`Invoice ${result.invoice.doc_no} posted.`);
      if (result.credit_limit_warning) {
        showToast('warning', 'Credit limit exceeded', 'The invoice was posted in WARN mode.');
      }
      setDeliveryId('');
      setDocDate(today());
      setDueDate(today());
      try {
        await reload();
      } catch (cause) {
        const message =
          cause instanceof Error
            ? `Invoice posted, but history could not be refreshed: ${cause.message}`
            : 'Invoice posted, but history could not be refreshed.';
        setError(message);
        showErrorToast(message);
      }
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not post the invoice';
      setError(message);
      showErrorToast(message);
    } finally {
      setSaving(false);
    }
  }

  if (!canRead) {
    return (
      <p className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
        Your account does not have permission to view sales invoices.
      </p>
    );
  }

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Sales Invoices</h1>
        <p className="mt-1 text-sm text-slate-600">
          Post one invoice for each delivery. Posting increases the customer due and stores the
          delivery&apos;s sale price and COGS.
        </p>
      </header>

      {error && <FieldError id="sales-invoice-error" message={error} />}

      {canCreate && (
        <form
          onSubmit={(event) => void submit(event)}
          className="grid gap-4 rounded-xl border border-slate-200 bg-white p-5 md:grid-cols-2"
        >
          <label className="text-sm font-medium text-slate-700">
            Posted delivery<RequiredMark />
            <SearchableSelect
              aria-label="Posted delivery"
              required
              placeholder="Search delivery or sales order"
              value={deliveryId}
              onChange={setDeliveryId}
              options={options.deliveries.map((delivery) => ({
                value: String(delivery.id),
                label: `${delivery.doc_no} · ${delivery.order_doc_no} · ${delivery.doc_date}`,
                searchText: `${delivery.doc_no} ${delivery.order_doc_no} ${delivery.doc_date}`,
              }))}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Invoice date<RequiredMark />
            <input
              aria-label="Invoice date"
              type="date"
              required
              value={docDate}
              onChange={(event) => setDocDate(event.target.value)}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Due date<RequiredMark />
            <input
              aria-label="Due date"
              type="date"
              required
              value={dueDate}
              onChange={(event) => setDueDate(event.target.value)}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            />
          </label>
          <div className="flex items-end">
            <button
              type="submit"
              disabled={saving || options.deliveries.length === 0}
              className="min-h-10 rounded-lg bg-emerald-700 px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? 'Posting…' : 'Post invoice'}
            </button>
          </div>
          {options.deliveries.length === 0 && (
            <p className="text-sm text-slate-600 md:col-span-2">
              There are no uninvoiced deliveries.
            </p>
          )}
        </form>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-5 py-4">
          <h2 className="font-semibold text-slate-900">Invoice History</h2>
        </div>
        {loading ? (
          <p className="p-5 text-sm text-slate-600">Loading invoices…</p>
        ) : invoices.length === 0 ? (
          <p className="p-5 text-sm text-slate-600">No invoices found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-slate-600">
                <tr>
                  <th className="px-4 py-3">Invoice</th>
                  <th className="px-4 py-3">Invoice / Due date</th>
                  <th className="px-4 py-3">Customer / Delivery</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Total / COGS</th>
                  <th className="px-4 py-3">Lines</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {invoices.map((invoice) => (
                  <tr key={invoice.id}>
                    <td className="px-4 py-3 font-medium text-slate-900">{invoice.doc_no}</td>
                    <td className="px-4 py-3">
                      {invoice.doc_date} / {invoice.due_date}
                    </td>
                    <td className="px-4 py-3">
                      Customer {invoice.customer_id} / delivery {invoice.delivery_id}
                    </td>
                    <td className="px-4 py-3">{invoice.status}</td>
                    <td className="px-4 py-3 text-right">
                      {invoice.total} / {invoice.cogs_total}
                    </td>
                    <td className="px-4 py-3">
                      <ul className="space-y-1 text-xs text-slate-600">
                        {invoice.lines.map((line) => (
                          <li key={line.id}>
                            Product {line.product_id}: {line.qty} × {line.unit_price}; COGS/unit{' '}
                            {line.unit_cost_cogs}
                          </li>
                        ))}
                      </ul>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}

export default function SalesInvoicesPage() {
  return (
    <ProtectedPage>
      <SalesInvoicesContent />
    </ProtectedPage>
  );
}
