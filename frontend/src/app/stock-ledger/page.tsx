'use client';

import { useEffect, useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { RequiredMark } from '@/components/forms/field-error';
import { SearchableSelect } from '@/components/forms/searchable-select';
import { useSessionProfile } from '@/components/auth/session-shell';
import { apiRequest } from '@/lib/auth-api';
import { showErrorToast } from '@/lib/notifications';

type WarehouseOption = {
  id: number;
  code: string;
  name: string;
};

type ProductOption = {
  id: number;
  sku: string;
  name: string;
  unit_code: string;
};

type StockLedgerEntry = {
  id: number;
  txn_date: string;
  product_id: number;
  warehouse_id: number;
  movement_type: string;
  qty_signed: string;
  unit_cost: string | null;
  source_type: string | null;
  source_id: number | null;
  source_line_id: number | null;
  note: string | null;
  running_qty: string;
};

const PAGE_SIZE = 50;

function StockLedgerContent() {
  const profile = useSessionProfile();
  const canRead = profile?.permissions.includes('inventory.stock.read') ?? false;
  const [warehouses, setWarehouses] = useState<WarehouseOption[]>([]);
  const [products, setProducts] = useState<ProductOption[]>([]);
  const [entries, setEntries] = useState<StockLedgerEntry[]>([]);
  const [productId, setProductId] = useState('');
  const [warehouseId, setWarehouseId] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [offset, setOffset] = useState(0);
  const [loadingOptions, setLoadingOptions] = useState(true);
  const [loadingEntries, setLoadingEntries] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!canRead) return;
    let active = true;
    apiRequest<{ products: ProductOption[]; warehouses: WarehouseOption[] }>(
      '/api/v1/inventory/ledger/options',
    )
      .then((options) => {
        if (!active) return;
        setProducts(options.products);
        setWarehouses(options.warehouses);
      })
      .catch((cause: unknown) => {
        if (!active) return;
        const message = cause instanceof Error ? cause.message : 'Could not load ledger options';
        setError(message);
        showErrorToast(message);
      })
      .finally(() => {
        if (active) setLoadingOptions(false);
      });
    return () => {
      active = false;
    };
  }, [canRead]);

  async function loadLedger(
    nextOffset: number,
    filters: { productId: string; warehouseId: string; dateFrom: string; dateTo: string },
  ) {
    if (!filters.productId) {
      setEntries([]);
      setError('Choose a product to view its stock ledger.');
      return;
    }
    if (filters.dateFrom && filters.dateTo && filters.dateFrom > filters.dateTo) {
      setError('Start date cannot be after end date.');
      return;
    }
    const params = new URLSearchParams({
      product_id: filters.productId,
      offset: String(nextOffset),
      limit: String(PAGE_SIZE),
    });
    if (filters.warehouseId) params.set('warehouse_id', filters.warehouseId);
    if (filters.dateFrom) params.set('date_from', filters.dateFrom);
    if (filters.dateTo) params.set('date_to', filters.dateTo);

    setLoadingEntries(true);
    setError('');
    try {
      const result = await apiRequest<StockLedgerEntry[]>(
        `/api/v1/inventory/ledger?${params.toString()}`,
      );
      setEntries(result);
      setOffset(nextOffset);
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not load stock ledger';
      setError(message);
      showErrorToast(message);
    } finally {
      setLoadingEntries(false);
    }
  }

  function submitFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void loadLedger(0, { productId, warehouseId, dateFrom, dateTo });
  }

  function clearFilters() {
    setProductId('');
    setWarehouseId('');
    setDateFrom('');
    setDateTo('');
    setEntries([]);
    setOffset(0);
    setError('');
  }

  if (!canRead) {
    return (
      <section className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
        Your account does not have permission to view the stock ledger.
      </section>
    );
  }

  function sourceLink(entry: StockLedgerEntry) {
    if (entry.source_id === null || entry.source_type === null) return null;
    const path =
      entry.source_type === 'STOCK_TRANSFER'
        ? `/stock-transfers?document_id=${entry.source_id}`
        : entry.source_type === 'STOCK_ADJUSTMENT'
          ? `/stock-adjustments?document_id=${entry.source_id}`
          : null;
    const label = `${entry.source_type} #${entry.source_id}`;
    return path ? (
      <a className="font-medium text-emerald-700 hover:underline" href={path}>
        {label}
      </a>
    ) : (
      label
    );
  }

  const selectedProduct = products.find((product) => String(product.id) === productId);

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Product Stock Ledger</h1>
        <p className="mt-1 text-sm text-slate-600">
          Review stock movements and the running on-hand balance for a product.
        </p>
      </header>

      <form
        onSubmit={submitFilters}
        className="grid gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm md:grid-cols-2 xl:grid-cols-5"
      >
        <label className="block text-sm font-medium text-slate-700">
          Product<RequiredMark />
          <SearchableSelect
            aria-label="Product"
            required
            value={productId}
            placeholder="Search product by SKU or name"
            onChange={setProductId}
            options={products.map((product) => ({
              value: String(product.id),
              label: `${product.name} (${product.sku})`,
              searchText: `${product.name} ${product.sku}`,
            }))}
            disabled={loadingOptions}
            className="mt-1.5 block min-h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm"
          />
        </label>
        <label className="block text-sm font-medium text-slate-700">
          Warehouse
          <SearchableSelect
            aria-label="Warehouse"
            value={warehouseId}
            placeholder="All warehouses or search"
            onChange={setWarehouseId}
            options={warehouses.map((warehouse) => ({
              value: String(warehouse.id),
              label: `${warehouse.name} (${warehouse.code})`,
              searchText: `${warehouse.name} ${warehouse.code}`,
            }))}
            disabled={loadingOptions}
            className="mt-1.5 block min-h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm"
          />
        </label>
        <label className="block text-sm font-medium text-slate-700">
          From date
          <input
            aria-label="From date"
            type="date"
            value={dateFrom}
            onChange={(event) => setDateFrom(event.target.value)}
            className="mt-1.5 block min-h-10 w-full rounded-lg border border-slate-300 px-3 text-sm"
          />
        </label>
        <label className="block text-sm font-medium text-slate-700">
          To date
          <input
            aria-label="To date"
            type="date"
            value={dateTo}
            onChange={(event) => setDateTo(event.target.value)}
            className="mt-1.5 block min-h-10 w-full rounded-lg border border-slate-300 px-3 text-sm"
          />
        </label>
        <div className="flex items-end gap-2">
          <button
            type="submit"
            disabled={loadingEntries || loadingOptions}
            className="min-h-10 rounded-lg bg-emerald-700 px-4 text-sm font-medium text-white hover:bg-emerald-800 disabled:opacity-50"
          >
            Search
          </button>
          <button
            type="button"
            onClick={clearFilters}
            className="min-h-10 rounded-lg border border-slate-300 px-4 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Clear
          </button>
        </div>
      </form>

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
          <h2 className="font-semibold text-slate-900">
            {selectedProduct
              ? `${selectedProduct.name} (${selectedProduct.sku})`
              : 'Stock movements'}
          </h2>
          {selectedProduct && (
            <p className="mt-1 text-xs text-slate-500">Unit: {selectedProduct.unit_code}</p>
          )}
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">Warehouse</th>
                <th className="px-4 py-3">Movement</th>
                <th className="px-4 py-3 text-right">Quantity</th>
                <th className="px-4 py-3 text-right">Running balance</th>
                <th className="px-4 py-3">Source</th>
                <th className="px-4 py-3">Note</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {entries.map((entry) => (
                <tr key={entry.id}>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                    {new Date(entry.txn_date).toLocaleString()}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                    {warehouses.find((warehouse) => warehouse.id === entry.warehouse_id)?.name ??
                      `Warehouse ${entry.warehouse_id}`}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                    {entry.movement_type}
                  </td>
                  <td
                    className={`whitespace-nowrap px-4 py-3 text-right font-medium ${
                      Number(entry.qty_signed) < 0 ? 'text-rose-700' : 'text-emerald-700'
                    }`}
                  >
                    {entry.qty_signed}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right font-medium text-slate-900">
                    {entry.running_qty}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                    {sourceLink(entry) ?? '—'}
                  </td>
                  <td className="max-w-64 px-4 py-3 text-slate-600">{entry.note ?? '—'}</td>
                </tr>
              ))}
              {!loadingEntries && productId && entries.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-slate-500">
                    No stock movements match these filters.
                  </td>
                </tr>
              )}
              {loadingEntries && (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-slate-500" role="status">
                    Loading stock ledger…
                  </td>
                </tr>
              )}
              {!productId && !loadingEntries && (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-slate-500">
                    Choose a product and search to view stock movements.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <footer className="flex items-center justify-between border-t border-slate-200 px-4 py-3">
          <span className="text-xs text-slate-500">
            {entries.length ? `Showing ${offset + 1}–${offset + entries.length}` : 'No movements'}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={!productId || offset === 0 || loadingEntries}
              onClick={() =>
                void loadLedger(Math.max(0, offset - PAGE_SIZE), {
                  productId,
                  warehouseId,
                  dateFrom,
                  dateTo,
                })
              }
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-50"
            >
              Previous
            </button>
            <button
              type="button"
              disabled={!productId || entries.length < PAGE_SIZE || loadingEntries}
              onClick={() =>
                void loadLedger(offset + PAGE_SIZE, { productId, warehouseId, dateFrom, dateTo })
              }
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

export default function StockLedgerPage() {
  return (
    <ProtectedPage>
      <StockLedgerContent />
    </ProtectedPage>
  );
}
