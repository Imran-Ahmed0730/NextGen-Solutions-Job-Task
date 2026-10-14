'use client';

import { useCallback, useEffect, useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { useSessionProfile } from '@/components/auth/session-shell';
import { apiRequest } from '@/lib/auth-api';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';
import { stockAdjustmentSchema } from '@/lib/auth-validation';

type WarehouseOption = {
  id: number;
  code: string;
  name: string;
};

type ProductOption = {
  id: number;
  sku: string;
  name: string;
  unit_code: string | null;
  is_stocked: boolean;
};

type AdjustmentLineInput = {
  product_id: string;
  direction: 'IN' | 'OUT';
  qty: string;
};

type AdjustmentLine = {
  id: number;
  product_id: number;
  qty_signed: string;
  unit_cost: string;
};

type StockAdjustment = {
  id: number;
  doc_no: string;
  doc_date: string;
  warehouse_id: number;
  reason: string;
  status: string;
  lines: AdjustmentLine[];
};

const PAGE_SIZE = 50;

function today(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(
    now.getDate(),
  ).padStart(2, '0')}`;
}

function StockAdjustmentsContent() {
  const profile = useSessionProfile();
  const canRead = profile?.permissions.includes('inventory.adjustments.read') ?? false;
  const canCreate = profile?.permissions.includes('inventory.adjustments.create') ?? false;
  const [warehouses, setWarehouses] = useState<WarehouseOption[]>([]);
  const [products, setProducts] = useState<ProductOption[]>([]);
  const [adjustments, setAdjustments] = useState<StockAdjustment[]>([]);
  const [linkedAdjustment, setLinkedAdjustment] = useState<StockAdjustment | null>(null);
  const [warehouseId, setWarehouseId] = useState('');
  const [docDate, setDocDate] = useState(today);
  const [reason, setReason] = useState('');
  const [lines, setLines] = useState<AdjustmentLineInput[]>([
    { product_id: '', direction: 'IN', qty: '' },
  ]);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const reloadAdjustments = useCallback(async (pageOffset: number) => {
    const params = new URLSearchParams({
      offset: String(pageOffset),
      limit: String(PAGE_SIZE),
    });
    setAdjustments(
      await apiRequest<StockAdjustment[]>(
        `/api/v1/inventory/adjustments?${params.toString()}`,
      ),
    );
  }, []);

  useEffect(() => {
    if (!canRead) return;
    let active = true;
    setLoading(true);
    Promise.all([
      apiRequest<{
        warehouses: WarehouseOption[];
        products: ProductOption[];
      }>('/api/v1/inventory/adjustments/options'),
      apiRequest<StockAdjustment[]>(`/api/v1/inventory/adjustments?limit=${PAGE_SIZE}`),
    ])
      .then(async ([options, adjustmentList]) => {
        if (!active) return;
        setWarehouses(options.warehouses);
        setProducts(options.products.filter((product) => product.is_stocked));
        setAdjustments(adjustmentList);
        const documentId = new URLSearchParams(window.location.search).get('document_id');
        if (documentId) {
          const detail = await apiRequest<StockAdjustment>(
            `/api/v1/inventory/adjustments/${encodeURIComponent(documentId)}`,
          );
          if (active) setLinkedAdjustment(detail);
        }
      })
      .catch((cause: unknown) => {
        if (!active) return;
        const message = cause instanceof Error ? cause.message : 'Could not load adjustments';
        setError(message);
        showErrorToast(message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [canRead]);

  function updateLine(index: number, key: keyof AdjustmentLineInput, value: string) {
    setLines((current) =>
      current.map((line, lineIndex) =>
        lineIndex === index ? { ...line, [key]: value } : line,
      ),
    );
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = stockAdjustmentSchema.safeParse({
      doc_date: docDate,
      warehouse_id: Number(warehouseId),
      reason,
      lines: lines.map((line) => ({
        product_id: Number(line.product_id),
        qty_signed: line.direction === 'IN' ? line.qty : `-${line.qty}`,
      })),
    });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? 'Check the adjustment fields and try again.');
      return;
    }

    setError('');
    setSaving(true);
    try {
      const posted = await apiRequest<StockAdjustment>('/api/v1/inventory/adjustments', {
        method: 'POST',
        body: JSON.stringify(parsed.data),
      });
      showSuccessToast(`Adjustment ${posted.doc_no} posted.`);
      setReason('');
      setLines([{ product_id: '', direction: 'IN', qty: '' }]);
      setOffset(0);
      try {
        await reloadAdjustments(0);
      } catch (cause) {
        const message =
          cause instanceof Error ? cause.message : 'Adjustment posted, but list refresh failed';
        setError(message);
        showErrorToast(message);
      }
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not post stock adjustment';
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
      await reloadAdjustments(nextOffset);
      setOffset(nextOffset);
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not load adjustments';
      setError(message);
      showErrorToast(message);
    } finally {
      setLoading(false);
    }
  }

  if (!canRead) {
    return (
      <section className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
        Your account does not have permission to view stock adjustments.
      </section>
    );
  }

  const warehouseName = (id: number) =>
    warehouses.find((warehouse) => warehouse.id === id)?.name ?? `Warehouse ${id}`;

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Stock Adjustments</h1>
        <p className="mt-1 text-sm text-slate-600">
          Record stock increases or decreases with a reason. Posted adjustments cannot be edited.
        </p>
      </header>

      {linkedAdjustment && (
        <aside className="rounded-xl border border-emerald-200 bg-emerald-50 p-5">
          <h2 className="font-semibold text-emerald-950">
            Linked adjustment: {linkedAdjustment.doc_no}
          </h2>
          <p className="mt-1 text-sm text-emerald-900">
            {linkedAdjustment.doc_date} · {warehouseName(linkedAdjustment.warehouse_id)} ·{' '}
            {linkedAdjustment.reason}
          </p>
          <ul className="mt-2 list-inside list-disc text-sm text-emerald-900">
            {linkedAdjustment.lines.map((line) => (
              <li key={line.id}>
                {products.find((product) => product.id === line.product_id)?.name ??
                  `Product ${line.product_id}`}{' '}
                {Number(line.qty_signed) > 0 ? '+' : ''}
                {line.qty_signed}
              </li>
            ))}
          </ul>
        </aside>
      )}

      {canCreate && (
        <form
          onSubmit={(event) => void submit(event)}
          className="space-y-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
        >
          <h2 className="text-lg font-semibold text-slate-900">New adjustment</h2>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="text-sm font-medium text-slate-700">
              Adjustment date
              <input
                aria-label="Adjustment date"
                required
                type="date"
                value={docDate}
                onChange={(event) => setDocDate(event.target.value)}
                className="mt-1.5 block min-h-10 w-full rounded-lg border border-slate-300 px-3 text-sm"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Warehouse
              <select
                aria-label="Warehouse"
                required
                value={warehouseId}
                onChange={(event) => setWarehouseId(event.target.value)}
                className="mt-1.5 block min-h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm"
              >
                <option value="">Select warehouse</option>
                {warehouses.map((warehouse) => (
                  <option key={warehouse.id} value={warehouse.id}>
                    {warehouse.name} ({warehouse.code})
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="space-y-3">
            <div className="grid grid-cols-[minmax(0,2fr)_minmax(8rem,1fr)_minmax(8rem,1fr)_auto] gap-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
              <span>Product</span>
              <span>Direction</span>
              <span>Quantity</span>
              <span className="sr-only">Actions</span>
            </div>
            {lines.map((line, index) => {
              const selectedIds = new Set(
                lines
                  .filter((_, lineIndex) => lineIndex !== index)
                  .map((item) => item.product_id),
              );
              return (
                <div
                  className="grid grid-cols-[minmax(0,2fr)_minmax(8rem,1fr)_minmax(8rem,1fr)_auto] gap-3"
                  key={`adjustment-line-${index}`}
                >
                  <select
                    aria-label={`Product ${index + 1}`}
                    required
                    value={line.product_id}
                    onChange={(event) => updateLine(index, 'product_id', event.target.value)}
                    className="min-h-10 min-w-0 rounded-lg border border-slate-300 bg-white px-3 text-sm"
                  >
                    <option value="">Select stocked product</option>
                    {products
                      .filter(
                        (product) =>
                          !selectedIds.has(String(product.id)) ||
                          String(product.id) === line.product_id,
                      )
                      .map((product) => (
                        <option key={product.id} value={product.id}>
                          {product.name} ({product.sku})
                        </option>
                      ))}
                  </select>
                  <select
                    aria-label={`Direction ${index + 1}`}
                    value={line.direction}
                    onChange={(event) =>
                      updateLine(index, 'direction', event.target.value === 'OUT' ? 'OUT' : 'IN')
                    }
                    className="min-h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm"
                  >
                    <option value="IN">Increase</option>
                    <option value="OUT">Decrease</option>
                  </select>
                  <input
                    aria-label={`Quantity ${index + 1}`}
                    required
                    type="number"
                    min="0.001"
                    step="0.001"
                    value={line.qty}
                    onChange={(event) => updateLine(index, 'qty', event.target.value)}
                    placeholder="0.000"
                    className="min-h-10 rounded-lg border border-slate-300 px-3 text-sm"
                  />
                  <button
                    type="button"
                    aria-label={`Remove product ${index + 1}`}
                    disabled={lines.length === 1}
                    onClick={() =>
                      setLines((current) => current.filter((_, lineIndex) => lineIndex !== index))
                    }
                    className="rounded-lg border border-slate-300 px-3 text-sm text-slate-700 disabled:opacity-40"
                  >
                    Remove
                  </button>
                </div>
              );
            })}
            <button
              type="button"
              onClick={() =>
                setLines((current) => [
                  ...current,
                  { product_id: '', direction: 'IN', qty: '' },
                ])
              }
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Add product
            </button>
          </div>

          <label className="block text-sm font-medium text-slate-700">
            Reason
            <textarea
              aria-label="Adjustment reason"
              required
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              maxLength={500}
              rows={2}
              className="mt-1.5 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </label>
          <button
            type="submit"
            disabled={saving || warehouses.length === 0 || products.length === 0}
            className="min-h-10 rounded-lg bg-emerald-700 px-4 text-sm font-semibold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {saving ? 'Posting…' : 'Post adjustment'}
          </button>
        </form>
      )}

      {error && (
        <div
          role="alert"
          className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800"
        >
          {error}
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 px-5 py-4">
          <h2 className="font-semibold text-slate-900">Recent adjustments</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Document</th>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">Warehouse</th>
                <th className="px-4 py-3">Reason</th>
                <th className="px-4 py-3">Products</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {adjustments.map((adjustment) => (
                <tr id={`stock-adjustment-${adjustment.id}`} key={adjustment.id}>
                  <td className="whitespace-nowrap px-4 py-3 font-medium text-slate-900">
                    {adjustment.doc_no}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                    {adjustment.doc_date}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                    {warehouseName(adjustment.warehouse_id)}
                  </td>
                  <td className="max-w-64 px-4 py-3 text-slate-600">{adjustment.reason}</td>
                  <td className="px-4 py-3 text-slate-600">
                    {adjustment.lines
                      .map((line) => {
                        const product = products.find((item) => item.id === line.product_id);
                        const direction = Number(line.qty_signed) > 0 ? '+' : '';
                        return `${product?.sku ?? `Product ${line.product_id}`} ${direction}${line.qty_signed}`;
                      })
                      .join(', ')}
                  </td>
                  <td className="px-4 py-3">
                    <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-800">
                      {adjustment.status}
                    </span>
                  </td>
                </tr>
              ))}
              {!loading && adjustments.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-slate-500">
                    No stock adjustments have been posted.
                  </td>
                </tr>
              )}
              {loading && (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-slate-500" role="status">
                    Loading adjustments…
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <footer className="flex items-center justify-between border-t border-slate-200 px-4 py-3">
          <span className="text-xs text-slate-500">
            {adjustments.length
              ? `Showing ${offset + 1}–${offset + adjustments.length}`
              : 'No adjustments'}
          </span>
          <div className="flex gap-2">
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
              disabled={adjustments.length < PAGE_SIZE || loading}
              onClick={() => void changePage(offset + PAGE_SIZE)}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </footer>
      </div>
    </section>
  );
}

export default function StockAdjustmentsPage() {
  return (
    <ProtectedPage>
      <StockAdjustmentsContent />
    </ProtectedPage>
  );
}
