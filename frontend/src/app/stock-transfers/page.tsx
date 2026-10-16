'use client';

import { useCallback, useEffect, useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { RequiredMark } from '@/components/forms/field-error';
import { SearchableSelect } from '@/components/forms/searchable-select';
import { useSessionProfile } from '@/components/auth/session-shell';
import { apiRequest } from '@/lib/auth-api';
import { statusLabel } from '@/lib/display-labels';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';
import { stockTransferSchema } from '@/lib/auth-validation';

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

type TransferLineInput = {
  product_id: string;
  qty: string;
};

type TransferLine = {
  id: number;
  product_id: number;
  qty: string;
};

type StockTransfer = {
  id: number;
  doc_no: string;
  doc_date: string;
  from_warehouse_id: number;
  to_warehouse_id: number;
  status: string;
  note: string | null;
  lines: TransferLine[];
};

const PAGE_SIZE = 50;

function today(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(
    now.getDate(),
  ).padStart(2, '0')}`;
}

function StockTransfersContent() {
  const profile = useSessionProfile();
  const canRead = profile?.permissions.includes('inventory.transfers.read') ?? false;
  const canCreate = profile?.permissions.includes('inventory.transfers.create') ?? false;
  const [warehouses, setWarehouses] = useState<WarehouseOption[]>([]);
  const [products, setProducts] = useState<ProductOption[]>([]);
  const [transfers, setTransfers] = useState<StockTransfer[]>([]);
  const [linkedTransfer, setLinkedTransfer] = useState<StockTransfer | null>(null);
  const [fromWarehouseId, setFromWarehouseId] = useState('');
  const [toWarehouseId, setToWarehouseId] = useState('');
  const [docDate, setDocDate] = useState(today);
  const [note, setNote] = useState('');
  const [lines, setLines] = useState<TransferLineInput[]>([{ product_id: '', qty: '' }]);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const reloadTransfers = useCallback(async (pageOffset: number) => {
    const params = new URLSearchParams({
      offset: String(pageOffset),
      limit: String(PAGE_SIZE),
    });
    setTransfers(
      await apiRequest<StockTransfer[]>(`/api/v1/inventory/transfers?${params.toString()}`),
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
      }>('/api/v1/inventory/transfers/options'),
      apiRequest<StockTransfer[]>(`/api/v1/inventory/transfers?limit=${PAGE_SIZE}`),
    ])
      .then(async ([options, transferList]) => {
        if (!active) return;
        setWarehouses(options.warehouses);
        setProducts(options.products.filter((product) => product.is_stocked));
        setTransfers(transferList);
        const documentId = new URLSearchParams(window.location.search).get('document_id');
        if (documentId) {
          const detail = await apiRequest<StockTransfer>(
            `/api/v1/inventory/transfers/${encodeURIComponent(documentId)}`,
          );
          if (active) setLinkedTransfer(detail);
        }
      })
      .catch((cause: unknown) => {
        if (!active) return;
        const message = cause instanceof Error ? cause.message : 'Could not load stock transfers';
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

  function updateLine(index: number, key: keyof TransferLineInput, value: string) {
    setLines((current) =>
      current.map((line, lineIndex) =>
        lineIndex === index ? { ...line, [key]: value } : line,
      ),
    );
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = stockTransferSchema.safeParse({
      doc_date: docDate,
      from_warehouse_id: Number(fromWarehouseId),
      to_warehouse_id: Number(toWarehouseId),
      note: note.trim() || null,
      lines: lines.map((line) => ({
        product_id: Number(line.product_id),
        qty: line.qty,
      })),
    });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? 'Check the transfer fields and try again.');
      return;
    }

    setError('');
    setSaving(true);
    try {
      const posted = await apiRequest<StockTransfer>('/api/v1/inventory/transfers', {
        method: 'POST',
        body: JSON.stringify(parsed.data),
      });
      showSuccessToast(`Transfer ${posted.doc_no} posted.`);
      setLines([{ product_id: '', qty: '' }]);
      setNote('');
      setOffset(0);
      try {
        await reloadTransfers(0);
      } catch (cause) {
        const message =
          cause instanceof Error ? cause.message : 'Transfer posted, but list refresh failed';
        setError(message);
        showErrorToast(message);
      }
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not post stock transfer';
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
      await reloadTransfers(nextOffset);
      setOffset(nextOffset);
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not load stock transfers';
      setError(message);
      showErrorToast(message);
    } finally {
      setLoading(false);
    }
  }

  if (!canRead) {
    return (
      <section className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
        Your account does not have permission to view stock transfers.
      </section>
    );
  }

  const warehouseName = (id: number) =>
    warehouses.find((warehouse) => warehouse.id === id)?.name ?? `Warehouse ${id}`;

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Stock Transfers</h1>
        <p className="mt-1 text-sm text-slate-600">
          Post stock movements between warehouses. Both ledger entries are recorded together.
        </p>
      </header>

      {linkedTransfer && (
        <aside className="rounded-xl border border-emerald-200 bg-emerald-50 p-5">
          <h2 className="font-semibold text-emerald-950">
            Linked transfer: {linkedTransfer.doc_no}
          </h2>
          <p className="mt-1 text-sm text-emerald-900">
            {linkedTransfer.doc_date} · {warehouseName(linkedTransfer.from_warehouse_id)} →{' '}
            {warehouseName(linkedTransfer.to_warehouse_id)}
          </p>
          <ul className="mt-2 list-inside list-disc text-sm text-emerald-900">
            {linkedTransfer.lines.map((line) => (
              <li key={line.id}>
                {products.find((product) => product.id === line.product_id)?.name ??
                  `Product ${line.product_id}`}{' '}
                × {line.qty}
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
          <h2 className="text-lg font-semibold text-slate-900">New transfer</h2>
          <div className="grid gap-4 md:grid-cols-3">
            <label className="text-sm font-medium text-slate-700">
              Transfer date<RequiredMark />
              <input
                aria-label="Transfer date"
                required
                type="date"
                value={docDate}
                onChange={(event) => setDocDate(event.target.value)}
                className="mt-1.5 block min-h-10 w-full rounded-lg border border-slate-300 px-3 text-sm"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              From warehouse<RequiredMark />
              <SearchableSelect
                aria-label="From warehouse"
                required
                placeholder="Search source warehouse"
                value={fromWarehouseId}
                onChange={setFromWarehouseId}
                options={warehouses.map((warehouse) => ({
                  value: String(warehouse.id),
                  label: `${warehouse.name} (${warehouse.code})`,
                  searchText: `${warehouse.name} ${warehouse.code}`,
                }))}
                className="mt-1.5 block min-h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              To warehouse<RequiredMark />
              <SearchableSelect
                aria-label="To warehouse"
                required
                placeholder="Search destination warehouse"
                value={toWarehouseId}
                onChange={setToWarehouseId}
                options={warehouses
                  .filter((warehouse) => String(warehouse.id) !== fromWarehouseId)
                  .map((warehouse) => ({
                    value: String(warehouse.id),
                    label: `${warehouse.name} (${warehouse.code})`,
                    searchText: `${warehouse.name} ${warehouse.code}`,
                  }))}
                className="mt-1.5 block min-h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm"
              />
            </label>
          </div>

          <div className="space-y-3">
            <div className="grid grid-cols-[minmax(0,2fr)_minmax(8rem,1fr)_auto] gap-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
              <span>Product<RequiredMark /></span>
              <span>Quantity<RequiredMark /></span>
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
                  className="grid grid-cols-[minmax(0,2fr)_minmax(8rem,1fr)_auto] gap-3"
                  key={`transfer-line-${index}`}
                >
                  <SearchableSelect
                    aria-label={`Product ${index + 1}`}
                    required
                    placeholder="Search product by SKU or name"
                    value={line.product_id}
                    onChange={(value) => updateLine(index, 'product_id', value)}
                    options={products
                      .filter(
                        (product) =>
                          !selectedIds.has(String(product.id)) ||
                          String(product.id) === line.product_id,
                      )
                      .map((product) => ({
                        value: String(product.id),
                        label: `${product.name} (${product.sku})`,
                        searchText: `${product.name} ${product.sku}`,
                      }))}
                    className="min-h-10 min-w-0 rounded-lg border border-slate-300 bg-white px-3 text-sm"
                  />
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
              onClick={() => setLines((current) => [...current, { product_id: '', qty: '' }])}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Add product
            </button>
          </div>

          <label className="block text-sm font-medium text-slate-700">
            Note
            <textarea
              value={note}
              onChange={(event) => setNote(event.target.value)}
              maxLength={1000}
              rows={2}
              placeholder="Optional transfer note"
              className="mt-1.5 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </label>
          <button
            type="submit"
            disabled={saving || warehouses.length < 2 || products.length === 0}
            className="min-h-10 rounded-lg bg-emerald-700 px-4 text-sm font-semibold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {saving ? 'Posting…' : 'Post transfer'}
          </button>
        </form>
      )}

      {error && (
        <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
          {error}
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 px-5 py-4">
          <h2 className="font-semibold text-slate-900">Recent transfers</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Document</th>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">From</th>
                <th className="px-4 py-3">To</th>
                <th className="px-4 py-3">Products</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {transfers.map((transfer) => (
                <tr id={`stock-transfer-${transfer.id}`} key={transfer.id}>
                  <td className="whitespace-nowrap px-4 py-3 font-medium text-slate-900">
                    {transfer.doc_no}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                    {transfer.doc_date}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                    {warehouseName(transfer.from_warehouse_id)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                    {warehouseName(transfer.to_warehouse_id)}
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    {transfer.lines
                      .map((line) => {
                        const product = products.find((item) => item.id === line.product_id);
                        return `${product?.sku ?? `Product ${line.product_id}`} × ${line.qty}`;
                      })
                      .join(', ')}
                  </td>
                  <td className="px-4 py-3">
                    <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-800">
                      {statusLabel(transfer.status)}
                    </span>
                  </td>
                </tr>
              ))}
              {!loading && transfers.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-slate-500">
                    No stock transfers have been posted.
                  </td>
                </tr>
              )}
              {loading && (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-slate-500" role="status">
                    Loading transfers…
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <footer className="flex items-center justify-between border-t border-slate-200 px-4 py-3">
          <span className="text-xs text-slate-500">
            {transfers.length
              ? `Showing ${offset + 1}–${offset + transfers.length}`
              : 'No transfers'}
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
              disabled={transfers.length < PAGE_SIZE || loading}
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

export default function StockTransfersPage() {
  return (
    <ProtectedPage>
      <StockTransfersContent />
    </ProtectedPage>
  );
}
