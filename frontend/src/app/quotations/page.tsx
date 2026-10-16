'use client';

import { useCallback, useEffect, useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { useSessionProfile } from '@/components/auth/session-shell';
import { RequiredMark, FieldError } from '@/components/forms/field-error';
import { SearchableSelect } from '@/components/forms/searchable-select';
import { apiRequest } from '@/lib/auth-api';
import { quotationConversionSchema, quotationSchema } from '@/lib/auth-validation';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';

type CustomerOption = { id: number; code: string; name: string };
type WarehouseOption = { id: number; code: string; name: string };
type ProductOption = {
  id: number;
  sku: string;
  name: string;
  unit_code: string;
  allow_decimal: boolean;
};
type QuotationOptions = {
  customers: CustomerOption[];
  products: ProductOption[];
  warehouses: WarehouseOption[];
};
type DraftLine = { product_id: string; qty: string; unit_price: string };
type QuotationLine = {
  id: number;
  product_id: number;
  qty: string;
  unit_price: string;
  line_total: string;
};
type Quotation = {
  id: number;
  doc_no: string;
  doc_date: string;
  customer_id: number;
  valid_until: string | null;
  status: string;
  subtotal: string;
  discount: string;
  total: string;
  note: string | null;
  sales_order_id: number | null;
  lines: QuotationLine[];
};

const PAGE_SIZE = 50;
const emptyLine = (): DraftLine => ({ product_id: '', qty: '', unit_price: '' });

function today(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(
    now.getDate(),
  ).padStart(2, '0')}`;
}

function QuotationsContent() {
  const profile = useSessionProfile();
  const canRead = profile?.permissions.includes('sales.quotations.read') ?? false;
  const canCreate = profile?.permissions.includes('sales.quotations.create') ?? false;
  const canUpdate = profile?.permissions.includes('sales.quotations.update') ?? false;
  const canConvert = profile?.permissions.includes('sales.orders.create') ?? false;
  const [options, setOptions] = useState<QuotationOptions>({
    customers: [],
    products: [],
    warehouses: [],
  });
  const [quotations, setQuotations] = useState<Quotation[]>([]);
  const [docDate, setDocDate] = useState(today);
  const [customerId, setCustomerId] = useState('');
  const [validUntil, setValidUntil] = useState('');
  const [discount, setDiscount] = useState('0.00');
  const [note, setNote] = useState('');
  const [lines, setLines] = useState<DraftLine[]>([emptyLine()]);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [actionBusyId, setActionBusyId] = useState<number | null>(null);
  const [conversionQuotationId, setConversionQuotationId] = useState<number | null>(null);
  const [conversionDocDate, setConversionDocDate] = useState(today);
  const [conversionWarehouseId, setConversionWarehouseId] = useState('');
  const [conversionDeliveryDate, setConversionDeliveryDate] = useState('');
  const [error, setError] = useState('');

  const reload = useCallback(async (nextOffset = 0) => {
    const [loadedOptions, loadedQuotations] = await Promise.all([
      apiRequest<QuotationOptions>('/api/v1/sales/quotations/options'),
      apiRequest<Quotation[]>(
        `/api/v1/sales/quotations?offset=${nextOffset}&limit=${PAGE_SIZE + 1}`,
      ),
    ]);
    setOptions(loadedOptions);
    setQuotations(loadedQuotations.slice(0, PAGE_SIZE));
    setHasMore(loadedQuotations.length > PAGE_SIZE);
    setOffset(nextOffset);
  }, []);

  useEffect(() => {
    if (!canRead) return;
    let active = true;
    setLoading(true);
    reload()
      .catch((cause: unknown) => {
        if (!active) return;
        const message = cause instanceof Error ? cause.message : 'Could not load quotations';
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

  function resetForm() {
    setDocDate(today());
    setCustomerId('');
    setValidUntil('');
    setDiscount('0.00');
    setNote('');
    setLines([emptyLine()]);
    setEditingId(null);
    setError('');
  }

  function editQuotation(quotation: Quotation) {
    setEditingId(quotation.id);
    setDocDate(quotation.doc_date);
    setCustomerId(String(quotation.customer_id));
    setValidUntil(quotation.valid_until ?? '');
    setDiscount(quotation.discount);
    setNote(quotation.note ?? '');
    setLines(
      quotation.lines.map((line) => ({
        product_id: String(line.product_id),
        qty: line.qty,
        unit_price: line.unit_price,
      })),
    );
    setError('');
  }

  function updateLine(index: number, key: keyof DraftLine, value: string) {
    setLines((current) =>
      current.map((line, lineIndex) =>
        lineIndex === index ? { ...line, [key]: value } : line,
      ),
    );
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = quotationSchema.safeParse({
      doc_date: docDate,
      customer_id: Number(customerId),
      valid_until: validUntil,
      discount,
      note,
      lines: lines.map((line) => ({
        product_id: Number(line.product_id),
        qty: line.qty,
        unit_price: line.unit_price,
      })),
    });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? 'Check the quotation details.');
      return;
    }

    setError('');
    setSaving(true);
    try {
      const saved = await apiRequest<Quotation>(
        editingId
          ? `/api/v1/sales/quotations/${editingId}`
          : '/api/v1/sales/quotations',
        { method: editingId ? 'PUT' : 'POST', body: JSON.stringify(parsed.data) },
      );
      showSuccessToast(`Quotation ${saved.doc_no} ${editingId ? 'updated' : 'created'}.`);
      resetForm();
      try {
        await reload(0);
      } catch (cause) {
        const message =
          cause instanceof Error
            ? `Quotation saved, but the list could not be refreshed: ${cause.message}`
            : 'Quotation saved, but the list could not be refreshed.';
        setError(message);
        showErrorToast(message);
      }
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not save quotation';
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
      const message = cause instanceof Error ? cause.message : 'Could not load quotations';
      setError(message);
      showErrorToast(message);
    } finally {
      setLoading(false);
    }
  }

  async function transitionQuotation(quotation: Quotation, action: 'send' | 'accept' | 'reject') {
    setActionBusyId(quotation.id);
    setError('');
    try {
      const updated = await apiRequest<Quotation>(
        `/api/v1/sales/quotations/${quotation.id}/${action}`,
        { method: 'POST' },
      );
      showSuccessToast(`Quotation ${updated.doc_no} ${updated.status.toLowerCase()}.`);
      try {
        await reload(offset);
      } catch (cause) {
        const message =
          cause instanceof Error
            ? `Quotation status updated, but the list could not be refreshed: ${cause.message}`
            : 'Quotation status updated, but the list could not be refreshed.';
        setError(message);
        showErrorToast(message);
      }
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not update quotation status';
      setError(message);
      showErrorToast(message);
    } finally {
      setActionBusyId(null);
    }
  }

  async function convertQuotation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (conversionQuotationId === null) return;
    const parsed = quotationConversionSchema.safeParse({
      doc_date: conversionDocDate,
      warehouse_id: Number(conversionWarehouseId),
      delivery_date: conversionDeliveryDate,
    });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? 'Check the sales order details.');
      return;
    }
    setError('');
    setSaving(true);
    try {
      const order = await apiRequest<{ doc_no: string }>(
        `/api/v1/sales/quotations/${conversionQuotationId}/convert`,
        { method: 'POST', body: JSON.stringify(parsed.data) },
      );
      showSuccessToast(`Sales order ${order.doc_no} created from the accepted quotation.`);
      setConversionQuotationId(null);
      setConversionDocDate(today());
      setConversionWarehouseId('');
      setConversionDeliveryDate('');
      try {
        await reload(offset);
      } catch (cause) {
        const message =
          cause instanceof Error
            ? `Sales order created, but the list could not be refreshed: ${cause.message}`
            : 'Sales order created, but the list could not be refreshed.';
        setError(message);
        showErrorToast(message);
      }
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not convert quotation';
      setError(message);
      showErrorToast(message);
    } finally {
      setSaving(false);
    }
  }

  if (!canRead) {
    return (
      <section className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
        Your account does not have permission to view quotations.
      </section>
    );
  }

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Quotations</h1>
        <p className="mt-1 text-sm text-slate-600">
          Create drafts, send them for customer review, record acceptance or rejection, and convert
          accepted quotations into a Sales Order once.
        </p>
      </header>

      {(canCreate || (editingId !== null && canUpdate)) && (
        <form onSubmit={submit} className="space-y-5 rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-lg font-semibold text-slate-900">
            {editingId ? 'Edit Draft Quotation' : 'New Quotation'}
          </h2>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-1 text-sm font-medium text-slate-700">
              <span>Quotation date <RequiredMark /></span>
              <input
                required
                type="date"
                value={docDate}
                onChange={(event) => setDocDate(event.target.value)}
                className="min-h-10 w-full rounded-lg border border-slate-300 px-3"
              />
            </label>
            <label className="space-y-1 text-sm font-medium text-slate-700">
              <span>Customer <RequiredMark /></span>
              <SearchableSelect
                required
                aria-label="Customer"
                value={customerId}
                onChange={setCustomerId}
                options={options.customers.map((customer) => ({
                  value: String(customer.id),
                  label: `${customer.code} - ${customer.name}`,
                }))}
                placeholder="Search or select a customer"
              />
            </label>
            <label className="space-y-1 text-sm font-medium text-slate-700">
              Valid until
              <input
                type="date"
                value={validUntil}
                onChange={(event) => setValidUntil(event.target.value)}
                className="mt-1 min-h-10 w-full rounded-lg border border-slate-300 px-3"
              />
            </label>
            <label className="space-y-1 text-sm font-medium text-slate-700">
              Discount
              <input
                inputMode="decimal"
                value={discount}
                onChange={(event) => setDiscount(event.target.value)}
                placeholder="0.00"
                className="mt-1 min-h-10 w-full rounded-lg border border-slate-300 px-3"
              />
            </label>
          </div>

          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-slate-800">
              Quotation lines <RequiredMark />
            </h3>
            {lines.map((line, index) => (
              <div key={index} className="grid gap-3 rounded-lg bg-slate-50 p-3 md:grid-cols-4">
                <label className="space-y-1 text-sm text-slate-700">
                  Product <RequiredMark />
                  <SearchableSelect
                    required
                    aria-label={`Product ${index + 1}`}
                    value={line.product_id}
                    onChange={(value) => updateLine(index, 'product_id', value)}
                    options={options.products.map((product) => ({
                      value: String(product.id),
                      label: `${product.sku} - ${product.name}`,
                    }))}
                    placeholder="Search or select product"
                  />
                </label>
                <label className="space-y-1 text-sm text-slate-700">
                  Quantity <RequiredMark />
                  <input
                    required
                    inputMode="decimal"
                    value={line.qty}
                    onChange={(event) => updateLine(index, 'qty', event.target.value)}
                    placeholder="Enter quantity"
                    className="min-h-10 w-full rounded-lg border border-slate-300 bg-white px-3"
                  />
                </label>
                <label className="space-y-1 text-sm text-slate-700">
                  Unit price <RequiredMark />
                  <input
                    required
                    inputMode="decimal"
                    value={line.unit_price}
                    onChange={(event) => updateLine(index, 'unit_price', event.target.value)}
                    placeholder="0.00"
                    className="min-h-10 w-full rounded-lg border border-slate-300 bg-white px-3"
                  />
                </label>
                <div className="flex items-end">
                  <button
                    type="button"
                    disabled={lines.length === 1}
                    onClick={() => setLines((current) => current.filter((_, i) => i !== index))}
                    className="min-h-10 rounded-lg border border-slate-300 px-3 text-sm text-slate-700 disabled:opacity-50"
                  >
                    Remove line
                  </button>
                </div>
              </div>
            ))}
            <button
              type="button"
              onClick={() => setLines((current) => [...current, emptyLine()])}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
            >
              Add line
            </button>
          </div>

          <label className="block space-y-1 text-sm font-medium text-slate-700">
            Note
            <textarea
              value={note}
              onChange={(event) => setNote(event.target.value)}
              maxLength={2000}
              rows={2}
              placeholder="Optional quotation note"
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
            />
          </label>
          {error && <FieldError id="quotation-error" message={error} />}
          <div className="flex gap-2">
            <button
              disabled={saving}
              className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {saving ? 'Saving…' : editingId ? 'Update Draft' : 'Save Draft'}
            </button>
            {editingId !== null && (
              <button
                type="button"
                onClick={resetForm}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700"
              >
                Cancel
              </button>
            )}
          </div>
        </form>
      )}

      {conversionQuotationId !== null && canConvert && (
        <form
          onSubmit={(event) => void convertQuotation(event)}
          className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
        >
          <h2 className="text-lg font-semibold text-slate-900">
            Convert quotation to Sales Order
          </h2>
          <div className="grid gap-4 md:grid-cols-3">
            <label className="text-sm font-medium text-slate-700">
              Order date<RequiredMark />
              <input
                aria-label="Order date"
                required
                type="date"
                value={conversionDocDate}
                onChange={(event) => setConversionDocDate(event.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Warehouse<RequiredMark />
              <SearchableSelect
                aria-label="Conversion warehouse"
                required
                placeholder="Search or select warehouse"
                value={conversionWarehouseId}
                onChange={setConversionWarehouseId}
                options={options.warehouses.map((warehouse) => ({
                  value: String(warehouse.id),
                  label: `${warehouse.code} - ${warehouse.name}`,
                }))}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Requested delivery date
              <input
                aria-label="Requested delivery date"
                type="date"
                value={conversionDeliveryDate}
                onChange={(event) => setConversionDeliveryDate(event.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
          </div>
          {error && <FieldError id="quotation-error" message={error} />}
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={saving}
              className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {saving ? 'Converting…' : 'Create Sales Order'}
            </button>
            <button
              type="button"
              disabled={saving}
              onClick={() => setConversionQuotationId(null)}
              className="rounded-md border border-slate-300 px-4 py-2 text-sm text-slate-700"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <h2 className="font-semibold text-slate-900">Quotation History</h2>
          <span className="text-sm text-slate-500">{quotations.length} shown</span>
        </div>
        {loading ? (
          <p className="p-5 text-sm text-slate-600">Loading quotations…</p>
        ) : quotations.length === 0 ? (
          <p className="p-5 text-sm text-slate-600">No quotations found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-slate-600">
                <tr>
                  <th className="px-4 py-3">Document</th>
                  <th className="px-4 py-3">Date</th>
                  <th className="px-4 py-3">Customer</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Total</th>
                  {(canUpdate || canConvert) && <th className="px-4 py-3">Action</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {quotations.map((quotation) => (
                  <tr key={quotation.id}>
                    <td className="px-4 py-3 font-medium text-slate-900">{quotation.doc_no}</td>
                    <td className="px-4 py-3">{quotation.doc_date}</td>
                    <td className="px-4 py-3">
                      {options.customers.find((item) => item.id === quotation.customer_id)?.name ??
                        `Customer ${quotation.customer_id}`}
                    </td>
                    <td className="px-4 py-3">{quotation.status}</td>
                    <td className="px-4 py-3 text-right">{quotation.total}</td>
                    {(canUpdate || canConvert) && (
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-2">
                          {canUpdate && quotation.status === 'DRAFT' && (
                            <>
                              <button
                                type="button"
                                onClick={() => editQuotation(quotation)}
                                className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-700"
                              >
                                Edit
                              </button>
                              <button
                                type="button"
                                disabled={actionBusyId === quotation.id}
                                onClick={() => void transitionQuotation(quotation, 'send')}
                                className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-700 disabled:opacity-50"
                              >
                                Send
                              </button>
                            </>
                          )}
                          {canUpdate && quotation.status === 'SENT' && (
                            <>
                              <button
                                type="button"
                                disabled={actionBusyId === quotation.id}
                                onClick={() => void transitionQuotation(quotation, 'accept')}
                                className="rounded-md border border-emerald-300 px-2 py-1 text-xs text-emerald-800 disabled:opacity-50"
                              >
                                Accept
                              </button>
                              <button
                                type="button"
                                disabled={actionBusyId === quotation.id}
                                onClick={() => void transitionQuotation(quotation, 'reject')}
                                className="rounded-md border border-rose-300 px-2 py-1 text-xs text-rose-800 disabled:opacity-50"
                              >
                                Reject
                              </button>
                            </>
                          )}
                          {canConvert && quotation.status === 'ACCEPTED' && (
                            quotation.sales_order_id ? (
                              <span className="text-xs text-slate-600">
                                Converted to Sales Order {quotation.sales_order_id}
                              </span>
                            ) : (
                              <button
                                type="button"
                                onClick={() => {
                                  setConversionQuotationId(quotation.id);
                                  setError('');
                                }}
                                className="rounded-md border border-emerald-300 px-2 py-1 text-xs text-emerald-800"
                              >
                                Convert
                              </button>
                            )
                          )}
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="flex items-center justify-between border-t border-slate-200 px-5 py-3">
          <button
            type="button"
            disabled={offset === 0 || loading}
            onClick={() => void changePage(Math.max(0, offset - PAGE_SIZE))}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-50"
          >
            Previous
          </button>
          <button
            type="button"
            disabled={!hasMore || loading}
            onClick={() => void changePage(offset + PAGE_SIZE)}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </div>
    </section>
  );
}

export default function QuotationsPage() {
  return (
    <ProtectedPage>
      <QuotationsContent />
    </ProtectedPage>
  );
}
