'use client';

import { useCallback, useEffect, useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { useSessionProfile } from '@/components/auth/session-shell';
import { apiRequest } from '@/lib/auth-api';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';
import { purchaseReturnSchema } from '@/lib/auth-validation';

type ReceiptLineOption = {
  receipt_line_id: number;
  product_id: number;
  product_sku: string;
  product_name: string;
  unit_code: string;
  allow_decimal: boolean;
  qty_received: string;
  qty_returned: string;
  qty_available: string;
  unit_cost: string;
};
type ReceiptOption = {
  id: number;
  doc_no: string;
  doc_date: string;
  supplier_id: number;
  supplier_name: string;
  warehouse_id: number;
  warehouse_name: string;
  lines: ReceiptLineOption[];
};
type PurchaseReturnOptions = { receipts: ReceiptOption[] };
type DraftLine = { receipt_line_id: number; qty: string };
type PurchaseReturnLine = {
  id: number;
  receipt_line_id: number;
  product_id: number;
  product_sku: string;
  product_name: string;
  qty: string;
  unit_cost: string;
  line_total: string;
};
type PurchaseReturn = {
  id: number;
  doc_no: string;
  doc_date: string;
  receipt_id: number;
  receipt_doc_no: string;
  supplier_id: number;
  warehouse_id: number;
  status: string;
  total: string;
  note: string | null;
  lines: PurchaseReturnLine[];
};

const PAGE_SIZE = 50;

function today(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(
    now.getDate(),
  ).padStart(2, '0')}`;
}

function PurchaseReturnsContent() {
  const profile = useSessionProfile();
  const canRead = profile?.permissions.includes('purchase.returns.read') ?? false;
  const canCreate = profile?.permissions.includes('purchase.returns.create') ?? false;
  const [options, setOptions] = useState<PurchaseReturnOptions>({ receipts: [] });
  const [returns, setReturns] = useState<PurchaseReturn[]>([]);
  const [selectedReceiptId, setSelectedReceiptId] = useState('');
  const [docDate, setDocDate] = useState(today);
  const [note, setNote] = useState('');
  const [lines, setLines] = useState<DraftLine[]>([]);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const reload = useCallback(async (nextOffset = 0) => {
    const [loadedOptions, loadedReturns] = await Promise.all([
      apiRequest<PurchaseReturnOptions>('/api/v1/purchase/returns/options'),
      apiRequest<PurchaseReturn[]>(
        `/api/v1/purchase/returns?offset=${nextOffset}&limit=${PAGE_SIZE + 1}`,
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
        const message = cause instanceof Error ? cause.message : 'Could not load purchase returns';
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

  function chooseReceipt(value: string) {
    setSelectedReceiptId(value);
    setError('');
    const receipt = options.receipts.find((candidate) => String(candidate.id) === value);
    setLines(
      receipt ? receipt.lines.map((line) => ({ receipt_line_id: line.receipt_line_id, qty: '' })) : [],
    );
  }

  function updateLine(index: number, value: string) {
    setLines((current) =>
      current.map((line, lineIndex) => (lineIndex === index ? { ...line, qty: value } : line)),
    );
  }

  function resetForm() {
    setSelectedReceiptId('');
    setDocDate(today());
    setNote('');
    setLines([]);
    setError('');
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = purchaseReturnSchema.safeParse({
      doc_date: docDate,
      receipt_id: Number(selectedReceiptId),
      note,
      lines: lines
        .filter((line) => line.qty.trim() !== '')
        .map((line) => ({ receipt_line_id: line.receipt_line_id, qty: line.qty })),
    });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? 'Check the purchase return details.');
      return;
    }

    setError('');
    setSaving(true);
    try {
      const posted = await apiRequest<PurchaseReturn>('/api/v1/purchase/returns', {
        method: 'POST',
        body: JSON.stringify(parsed.data),
      });
      showSuccessToast(`Purchase return ${posted.doc_no} posted.`);
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
      const message = cause instanceof Error ? cause.message : 'Could not post purchase return';
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
      const message = cause instanceof Error ? cause.message : 'Could not load purchase returns';
      setError(message);
      showErrorToast(message);
    } finally {
      setLoading(false);
    }
  }

  if (!canRead) {
    return (
      <section className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
        Your account does not have permission to view purchase returns.
      </section>
    );
  }

  const selectedReceipt = options.receipts.find(
    (receipt) => String(receipt.id) === selectedReceiptId,
  );
  const supplierName = (id: number) =>
    options.receipts.find((receipt) => receipt.supplier_id === id)?.supplier_name ??
    `Supplier ${id}`;
  const warehouseName = (id: number) =>
    options.receipts.find((receipt) => receipt.warehouse_id === id)?.warehouse_name ??
    `Warehouse ${id}`;

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Purchase Returns</h1>
        <p className="mt-1 text-sm text-slate-600">
          Return quantities from posted Goods Receipts only. Each return uses the original receipt
          cost, reduces stock, and reduces supplier due atomically.
        </p>
      </header>

      {canCreate && (
        <form
          onSubmit={(event) => void submit(event)}
          className="space-y-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
        >
          <h2 className="text-lg font-semibold text-slate-900">Post purchase return</h2>
          {options.receipts.length === 0 ? (
            <p className="rounded-md bg-amber-50 p-3 text-sm text-amber-900">
              No Goods Receipt lines have quantities remaining to return.
            </p>
          ) : (
            <>
              <div className="grid gap-4 md:grid-cols-2">
                <label className="text-sm font-medium text-slate-700">
                  Goods Receipt
                  <select
                    aria-label="Goods Receipt"
                    required
                    value={selectedReceiptId}
                    onChange={(event) => chooseReceipt(event.target.value)}
                    className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
                  >
                    <option value="">Select Goods Receipt</option>
                    {options.receipts.map((receipt) => (
                      <option key={receipt.id} value={receipt.id}>
                        {receipt.doc_no} — {receipt.supplier_name} ({receipt.doc_date})
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-sm font-medium text-slate-700">
                  Return date
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
                  <input
                    aria-label="Return note"
                    maxLength={2000}
                    value={note}
                    onChange={(event) => setNote(event.target.value)}
                    className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
                  />
                </label>
              </div>

              {selectedReceipt && (
                <div className="rounded-md bg-slate-50 p-3 text-sm text-slate-700">
                  Supplier: {selectedReceipt.supplier_name} · Warehouse:{' '}
                  {selectedReceipt.warehouse_name}
                </div>
              )}

              {lines.map((line, index) => {
                const sourceLine = selectedReceipt?.lines.find(
                  (candidate) => candidate.receipt_line_id === line.receipt_line_id,
                );
                if (!sourceLine) return null;
                return (
                  <div
                    key={line.receipt_line_id}
                    className="grid gap-3 rounded-lg border border-slate-200 p-3 md:grid-cols-[2fr_1fr_1fr]"
                  >
                    <div className="text-sm text-slate-700">
                      <p className="font-medium text-slate-900">
                        {sourceLine.product_sku} — {sourceLine.product_name}
                      </p>
                      <p className="mt-1">
                        Received {sourceLine.qty_received}; returned {sourceLine.qty_returned};
                        returnable {sourceLine.qty_available} {sourceLine.unit_code}
                      </p>
                      <p className="mt-1">Original unit cost {sourceLine.unit_cost}</p>
                    </div>
                    <label className="text-sm font-medium text-slate-700">
                      Return quantity ({sourceLine.unit_code})
                      <input
                        aria-label={`Return quantity ${index + 1}`}
                        type="number"
                        min="0"
                        step={sourceLine.allow_decimal ? '0.001' : '1'}
                        value={line.qty}
                        onChange={(event) => updateLine(index, event.target.value)}
                        className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
                      />
                    </label>
                    <p className="self-center text-sm text-slate-600">
                      Return value is calculated at the original unit cost.
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
                disabled={saving || !selectedReceipt || lines.length === 0}
                className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-800 disabled:opacity-60"
              >
                {saving ? 'Posting…' : 'Post return'}
              </button>
            </>
          )}
          {error && options.receipts.length === 0 && (
            <p role="alert" className="rounded-md bg-rose-50 p-3 text-sm text-rose-800">
              {error}
            </p>
          )}
        </form>
      )}

      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 px-5 py-4">
          <h2 className="font-semibold text-slate-900">Purchase return history</h2>
        </div>
        {loading ? (
          <p className="p-5 text-sm text-slate-600">Loading purchase returns…</p>
        ) : returns.length === 0 ? (
          <p className="p-5 text-sm text-slate-600">No purchase returns found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-600">
                <tr>
                  <th className="px-4 py-3">Return</th>
                  <th className="px-4 py-3">Date</th>
                  <th className="px-4 py-3">Goods Receipt</th>
                  <th className="px-4 py-3">Supplier</th>
                  <th className="px-4 py-3">Warehouse</th>
                  <th className="px-4 py-3 text-right">Total</th>
                  <th className="px-4 py-3">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {returns.map((purchaseReturn) => (
                  <tr key={purchaseReturn.id}>
                    <td className="px-4 py-3 font-medium text-slate-900">
                      {purchaseReturn.doc_no}
                    </td>
                    <td className="px-4 py-3">{purchaseReturn.doc_date}</td>
                    <td className="px-4 py-3">{purchaseReturn.receipt_doc_no}</td>
                    <td className="px-4 py-3">{supplierName(purchaseReturn.supplier_id)}</td>
                    <td className="px-4 py-3">{warehouseName(purchaseReturn.warehouse_id)}</td>
                    <td className="px-4 py-3 text-right">{purchaseReturn.total}</td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={() =>
                          setExpandedId((current) =>
                            current === purchaseReturn.id ? null : purchaseReturn.id,
                          )
                        }
                        className="font-medium text-emerald-800 hover:underline"
                      >
                        {expandedId === purchaseReturn.id ? 'Hide' : 'View'}
                      </button>
                    </td>
                  </tr>
                ))}
                {returns.map(
                  (purchaseReturn) =>
                    expandedId === purchaseReturn.id && (
                      <tr key={`lines-${purchaseReturn.id}`}>
                        <td colSpan={7} className="bg-slate-50 px-6 py-4">
                          <ul className="space-y-1">
                            {purchaseReturn.lines.map((line) => (
                              <li key={line.id} className="flex flex-wrap justify-between gap-2">
                                <span>
                                  {line.product_sku} — {line.product_name} {line.qty} ×{' '}
                                  {line.unit_cost}
                                </span>
                                <span>{line.line_total}</span>
                              </li>
                            ))}
                          </ul>
                          {purchaseReturn.note && (
                            <p className="mt-2 text-slate-600">Note: {purchaseReturn.note}</p>
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
              {returns.length ? `${offset + 1}–${offset + returns.length}` : '0'} returns
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

export default function PurchaseReturnsPage() {
  return (
    <ProtectedPage>
      <PurchaseReturnsContent />
    </ProtectedPage>
  );
}
