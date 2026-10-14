'use client';

import { useCallback, useEffect, useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { RequiredMark } from '@/components/forms/field-error';
import { SearchableSelect } from '@/components/forms/searchable-select';
import { useSessionProfile } from '@/components/auth/session-shell';
import { apiRequest } from '@/lib/auth-api';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';
import { goodsReceiptSchema } from '@/lib/auth-validation';

type ReceiptOrderLine = {
  po_line_id: number;
  product_id: number;
  product_sku: string;
  product_name: string;
  unit_code: string;
  allow_decimal: boolean;
  qty_ordered: string;
  received_qty: string;
  unit_price: string;
};
type ReceiptOrder = {
  id: number;
  doc_no: string;
  doc_date: string;
  supplier_id: number;
  supplier_name: string;
  warehouse_id: number;
  warehouse_name: string;
  status: string;
  lines: ReceiptOrderLine[];
};
type GoodsReceiptOptions = { orders: ReceiptOrder[] };
type ReceiptLineInput = { po_line_id: number; qty: string; unit_cost: string };
type GoodsReceiptLine = {
  id: number;
  po_line_id: number;
  product_id: number;
  product_sku: string;
  product_name: string;
  qty: string;
  unit_cost: string;
  line_total: string;
};
type GoodsReceipt = {
  id: number;
  doc_no: string;
  doc_date: string;
  po_id: number;
  supplier_id: number;
  warehouse_id: number;
  status: string;
  total: string;
  note: string | null;
  lines: GoodsReceiptLine[];
};

const PAGE_SIZE = 50;

function today(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(
    now.getDate(),
  ).padStart(2, '0')}`;
}

function subtractQuantity(left: string, right: string): string {
  const toMilliUnits = (value: string) => {
    const [whole, fraction = ''] = value.split('.');
    return `${whole}${fraction.padEnd(3, '0')}`.replace(/^0+(?=\d)/, '');
  };
  const minuend = toMilliUnits(left);
  const subtrahend = toMilliUnits(right);
  if (
    minuend.length < subtrahend.length ||
    (minuend.length === subtrahend.length && minuend < subtrahend)
  ) {
    return '0.000';
  }
  const digits = minuend.split('');
  let borrow = 0;
  for (let index = digits.length - 1; index >= 0; index -= 1) {
    let digit = Number(digits[index]) - borrow;
    const subtractDigit = index >= digits.length - subtrahend.length
      ? Number(subtrahend[index - (digits.length - subtrahend.length)])
      : 0;
    if (digit < subtractDigit) {
      digit += 10;
      borrow = 1;
    } else {
      borrow = 0;
    }
    digits[index] = String(digit - subtractDigit);
  }
  const result = digits.join('').replace(/^0+(?=\d)/, '').padStart(4, '0');
  return `${result.slice(0, -3)}.${result.slice(-3)}`;
}

function formatUnitCost(value: string): string {
  const [whole, fraction = ''] = value.split('.');
  return `${whole}.${fraction.padEnd(4, '0')}`;
}

function GoodsReceiptsContent() {
  const profile = useSessionProfile();
  const canRead = profile?.permissions.includes('purchase.receipts.read') ?? false;
  const canCreate = profile?.permissions.includes('purchase.receipts.create') ?? false;
  const [options, setOptions] = useState<GoodsReceiptOptions>({ orders: [] });
  const [receipts, setReceipts] = useState<GoodsReceipt[]>([]);
  const [selectedOrderId, setSelectedOrderId] = useState('');
  const [docDate, setDocDate] = useState(today);
  const [note, setNote] = useState('');
  const [lines, setLines] = useState<ReceiptLineInput[]>([]);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const reload = useCallback(async (nextOffset = 0) => {
    const [receiptOptions, receiptPage] = await Promise.all([
      apiRequest<GoodsReceiptOptions>('/api/v1/purchase/receipts/options'),
      apiRequest<GoodsReceipt[]>(
        `/api/v1/purchase/receipts?offset=${nextOffset}&limit=${PAGE_SIZE + 1}`,
      ),
    ]);
    setOptions(receiptOptions);
    setReceipts(receiptPage.slice(0, PAGE_SIZE));
    setHasMore(receiptPage.length > PAGE_SIZE);
    setOffset(nextOffset);
  }, []);

  useEffect(() => {
    if (!canRead) return;
    let active = true;
    setLoading(true);
    reload()
      .catch((cause: unknown) => {
        if (!active) return;
        const message = cause instanceof Error ? cause.message : 'Could not load goods receipts';
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

  function chooseOrder(value: string) {
    setSelectedOrderId(value);
    setError('');
    const order = options.orders.find((candidate) => String(candidate.id) === value);
    setLines(
      order
        ? order.lines
            .map((line) => ({
              po_line_id: line.po_line_id,
              qty:
                subtractQuantity(line.qty_ordered, line.received_qty) === '0.000'
                  ? ''
                  : subtractQuantity(line.qty_ordered, line.received_qty),
              unit_cost: formatUnitCost(line.unit_price),
            }))
        : [],
    );
  }

  function updateLine(index: number, key: 'qty' | 'unit_cost', value: string) {
    setLines((current) =>
      current.map((line, lineIndex) =>
        lineIndex === index ? { ...line, [key]: value } : line,
      ),
    );
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = goodsReceiptSchema.safeParse({
      doc_date: docDate,
      po_id: Number(selectedOrderId),
      note,
      lines: lines
        .filter((line) => line.qty.trim() !== '')
        .map((line) => ({
          po_line_id: line.po_line_id,
          qty: line.qty,
          unit_cost: line.unit_cost,
        })),
    });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? 'Check the goods receipt details.');
      return;
    }

    setError('');
    setSaving(true);
    try {
      const posted = await apiRequest<GoodsReceipt>('/api/v1/purchase/receipts', {
        method: 'POST',
        body: JSON.stringify(parsed.data),
      });
      showSuccessToast(`Goods receipt ${posted.doc_no} posted.`);
      setSelectedOrderId('');
      setDocDate(today());
      setNote('');
      setLines([]);
      try {
        await reload(0);
      } catch (cause) {
        const message =
          cause instanceof Error
            ? `Receipt posted, but the history could not be refreshed: ${cause.message}`
            : 'Receipt posted, but the history could not be refreshed.';
        setError(message);
        showErrorToast(message);
      }
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not post goods receipt';
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
      const message = cause instanceof Error ? cause.message : 'Could not load goods receipts';
      setError(message);
      showErrorToast(message);
    } finally {
      setLoading(false);
    }
  }

  if (!canRead) {
    return (
      <section className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
        Your account does not have permission to view goods receipts.
      </section>
    );
  }

  const selectedOrder = options.orders.find((order) => String(order.id) === selectedOrderId);
  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Goods Receipts</h1>
        <p className="mt-1 text-sm text-slate-600">
          Receive products only against approved purchase orders. Posting updates stock, weighted
          average cost, purchase-order received quantities, and supplier due atomically.
        </p>
      </header>

      {canCreate && (
        <form
          onSubmit={(event) => void submit(event)}
          className="space-y-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
        >
          <h2 className="text-lg font-semibold text-slate-900">Post goods receipt</h2>
          {options.orders.length === 0 ? (
            <p className="rounded-md bg-amber-50 p-3 text-sm text-amber-900">
              No approved or partially received purchase orders are available. Purchase-order
              submission and approval are scheduled for Phase 11.
            </p>
          ) : (
            <>
              <div className="grid gap-4 md:grid-cols-2">
                <label className="text-sm font-medium text-slate-700">
                  Purchase order<RequiredMark />
                  <SearchableSelect
                    aria-label="Purchase order"
                    required
                    placeholder="Search by document number or supplier"
                    value={selectedOrderId}
                    onChange={chooseOrder}
                    options={options.orders.map((order) => ({
                      value: String(order.id),
                      label: `${order.doc_no} — ${order.supplier_name} (${order.status})`,
                      searchText: `${order.doc_no} ${order.supplier_name} ${order.status}`,
                    }))}
                    className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
                  />
                </label>
                <label className="text-sm font-medium text-slate-700">
                  Receipt date<RequiredMark />
                  <input
                    aria-label="Receipt date"
                    type="date"
                    required
                    value={docDate}
                    onChange={(event) => setDocDate(event.target.value)}
                    className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
                  />
                </label>
                <label className="text-sm font-medium text-slate-700 md:col-span-2">
                  Note
                  <input
                    aria-label="Receipt note"
                    maxLength={2000}
                    value={note}
                    onChange={(event) => setNote(event.target.value)}
                    className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
                  />
                </label>
              </div>

              {selectedOrder && (
                <div className="rounded-md bg-slate-50 p-3 text-sm text-slate-700">
                  Supplier: {selectedOrder.supplier_name} · Warehouse: {selectedOrder.warehouse_name}
                </div>
              )}

              {lines.length > 0 ? (
                <div className="space-y-3">
                  {lines.map((line, index) => {
                    const orderLine = selectedOrder?.lines.find(
                      (candidate) => candidate.po_line_id === line.po_line_id,
                    );
                    return (
                      <div
                        key={line.po_line_id}
                        className="grid gap-3 rounded-lg border border-slate-200 p-3 md:grid-cols-[2fr_1fr_1fr]"
                      >
                        <div className="text-sm text-slate-700">
                          <p className="font-medium text-slate-900">
                            {orderLine?.product_sku} — {orderLine?.product_name}
                          </p>
                          <p className="mt-1">
                            Ordered {orderLine?.qty_ordered} {orderLine?.unit_code}; previously
                            received {orderLine?.received_qty}
                          </p>
                        </div>
                        <label className="text-sm font-medium text-slate-700">
                          Receive qty {orderLine ? `(${orderLine.unit_code})` : ''}
                          <input
                            aria-label={`Receive quantity ${index + 1}`}
                            type="number"
                            min="0"
                            step={orderLine?.allow_decimal ? '0.001' : '1'}
                            value={line.qty}
                            onChange={(event) => updateLine(index, 'qty', event.target.value)}
                            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
                          />
                        </label>
                        <label className="text-sm font-medium text-slate-700">
                          Unit cost
                          <input
                            aria-label={`Unit cost ${index + 1}`}
                            type="number"
                            min="0"
                            step="0.0001"
                            value={line.unit_cost}
                            onChange={(event) =>
                              updateLine(index, 'unit_cost', event.target.value)
                            }
                            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
                          />
                        </label>
                      </div>
                    );
                  })}
                </div>
              ) : (
                selectedOrder && (
                  <p className="rounded-md bg-emerald-50 p-3 text-sm text-emerald-900">
                    All ordered quantities have already been received.
                  </p>
                )
              )}
              {error && (
                <p role="alert" className="rounded-md bg-rose-50 p-3 text-sm text-rose-800">
                  {error}
                </p>
              )}
              <button
                type="submit"
                disabled={saving || !selectedOrder || lines.length === 0}
                className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-800 disabled:opacity-60"
              >
                {saving ? 'Posting…' : 'Post receipt'}
              </button>
            </>
          )}
          {error && options.orders.length === 0 && (
            <p role="alert" className="rounded-md bg-rose-50 p-3 text-sm text-rose-800">
              {error}
            </p>
          )}
        </form>
      )}

      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 px-5 py-4">
          <h2 className="font-semibold text-slate-900">Receipt history</h2>
        </div>
        {loading ? (
          <p className="p-5 text-sm text-slate-600">Loading goods receipts…</p>
        ) : receipts.length === 0 ? (
          <p className="p-5 text-sm text-slate-600">No goods receipts found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-600">
                <tr>
                  <th className="px-4 py-3">Receipt</th>
                  <th className="px-4 py-3">Date</th>
                  <th className="px-4 py-3">Purchase Order</th>
                  <th className="px-4 py-3 text-right">Total</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {receipts.map((receipt) => (
                  <tr key={receipt.id}>
                    <td className="px-4 py-3 font-medium text-slate-900">{receipt.doc_no}</td>
                    <td className="px-4 py-3">{receipt.doc_date}</td>
                    <td className="px-4 py-3">
                      {options.orders.find((order) => order.id === receipt.po_id)?.doc_no ??
                        `Purchase Order ${receipt.po_id}`}
                    </td>
                    <td className="px-4 py-3 text-right">{receipt.total}</td>
                    <td className="px-4 py-3">{receipt.status}</td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={() =>
                          setExpandedId((current) =>
                            current === receipt.id ? null : receipt.id,
                          )
                        }
                        className="font-medium text-emerald-800 hover:underline"
                      >
                        {expandedId === receipt.id ? 'Hide' : 'View'}
                      </button>
                    </td>
                  </tr>
                ))}
                {receipts.map(
                  (receipt) =>
                    expandedId === receipt.id && (
                      <tr key={`lines-${receipt.id}`}>
                        <td colSpan={6} className="bg-slate-50 px-6 py-4">
                          <ul className="space-y-1">
                            {receipt.lines.map((line) => (
                              <li key={line.id} className="flex flex-wrap justify-between gap-2">
                                <span>
                                  {line.product_sku} — {line.product_name}{' '}
                                  — {line.qty} × {line.unit_cost}
                                </span>
                                <span>{line.line_total}</span>
                              </li>
                            ))}
                          </ul>
                          {receipt.note && (
                            <p className="mt-2 text-slate-600">Note: {receipt.note}</p>
                          )}
                        </td>
                      </tr>
                    ),
                )}
              </tbody>
            </table>
          </div>
        )}
        {!loading && (
          <div className="flex items-center justify-between border-t border-slate-200 px-5 py-3">
            <button
              type="button"
              disabled={offset === 0}
              onClick={() => void changePage(Math.max(offset - PAGE_SIZE, 0))}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 disabled:opacity-50"
            >
              Previous
            </button>
            <span className="text-xs text-slate-500">
              {receipts.length ? `${offset + 1}–${offset + receipts.length}` : '0'} receipts
            </span>
            <button
              type="button"
              disabled={!hasMore}
              onClick={() => void changePage(offset + PAGE_SIZE)}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 disabled:opacity-50"
            >
              Next
            </button>
          </div>
        )}
      </section>
    </section>
  );
}

export default function GoodsReceiptsPage() {
  return (
    <ProtectedPage>
      <GoodsReceiptsContent />
    </ProtectedPage>
  );
}
