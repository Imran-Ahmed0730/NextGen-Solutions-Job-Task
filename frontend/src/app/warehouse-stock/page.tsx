'use client';

import { useEffect, useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { SearchableSelect } from '@/components/forms/searchable-select';
import { useSessionProfile } from '@/components/auth/session-shell';
import { apiRequest } from '@/lib/auth-api';
import { showErrorToast } from '@/lib/notifications';

type WarehouseOption = {
  id: number;
  code: string;
  name: string;
};

type WarehouseStockRow = {
  product_id: number;
  product_sku: string;
  product_name: string;
  unit_code: string;
  warehouse_id: number;
  warehouse_code: string;
  warehouse_name: string;
  qty_on_hand: string;
  qty_reserved: string;
  available: string;
};

const PAGE_SIZE = 50;

function WarehouseStockContent() {
  const profile = useSessionProfile();
  const [warehouses, setWarehouses] = useState<WarehouseOption[]>([]);
  const [rows, setRows] = useState<WarehouseStockRow[]>([]);
  const [warehouseId, setWarehouseId] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [offset, setOffset] = useState(0);
  const [loadingWarehouses, setLoadingWarehouses] = useState(true);
  const [loadingStock, setLoadingStock] = useState(true);
  const [warehouseError, setWarehouseError] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    apiRequest<WarehouseOption[]>('/api/v1/warehouses?limit=200')
      .then((result) => {
        if (active) {
          setWarehouses(result);
          setWarehouseError('');
        }
      })
      .catch((cause: unknown) => {
        if (!active) return;
        const message =
          cause instanceof Error ? cause.message : 'Could not load warehouse options';
        setWarehouseError(message);
        showErrorToast(message);
      })
      .finally(() => {
        if (active) setLoadingWarehouses(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    const params = new URLSearchParams({
      offset: String(offset),
      limit: String(PAGE_SIZE),
    });
    if (warehouseId) params.set('warehouse_id', warehouseId);
    if (search) params.set('search', search);

    setLoadingStock(true);
    apiRequest<WarehouseStockRow[]>(`/api/v1/inventory/warehouse-stock?${params}`)
      .then((result) => {
        if (!active) return;
        setRows(result);
        setError('');
      })
      .catch((cause: unknown) => {
        if (!active) return;
        const message = cause instanceof Error ? cause.message : 'Could not load warehouse stock';
        setError(message);
        showErrorToast(message);
      })
      .finally(() => {
        if (active) setLoadingStock(false);
      });
    return () => {
      active = false;
    };
  }, [offset, search, warehouseId]);

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setOffset(0);
    setSearch(searchInput.trim());
  }

  function changeWarehouse(value: string) {
    setWarehouseId(value);
    setOffset(0);
  }

  const canReadStock = profile?.permissions.includes('inventory.stock.read') ?? false;

  if (!canReadStock) {
    return (
      <section className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
        Your account does not have permission to view inventory stock.
      </section>
    );
  }

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Warehouse Stock</h1>
        <p className="mt-1 text-sm text-slate-600">
          Review on-hand, reserved, and available quantities by warehouse.
        </p>
      </header>

      <div className="grid gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm md:grid-cols-[minmax(14rem,1fr)_minmax(18rem,2fr)_auto] md:items-end">
        <label className="block text-sm font-medium text-slate-700">
          Warehouse
          <SearchableSelect
            aria-label="Warehouse"
            value={warehouseId}
            placeholder="All warehouses or search"
            onChange={changeWarehouse}
            options={warehouses.map((warehouse) => ({
              value: String(warehouse.id),
              label: `${warehouse.name} (${warehouse.code})`,
              searchText: `${warehouse.name} ${warehouse.code}`,
            }))}
            disabled={loadingWarehouses}
            className="mt-1.5 block min-h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-900 shadow-sm focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-600/20 disabled:bg-slate-100"
          />
        </label>

        <form onSubmit={submitSearch} className="flex items-end gap-2">
          <label className="block min-w-0 flex-1 text-sm font-medium text-slate-700">
            Product
            <input
              type="search"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Search by product name or SKU"
              className="mt-1.5 block min-h-10 w-full rounded-lg border border-slate-300 px-3 text-sm text-slate-900 shadow-sm placeholder:text-slate-500 focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-600/20"
            />
          </label>
          <button
            type="submit"
            className="min-h-10 rounded-lg bg-emerald-700 px-4 text-sm font-medium text-white hover:bg-emerald-800 focus:outline-none focus:ring-2 focus:ring-emerald-600 focus:ring-offset-2"
          >
            Search
          </button>
        </form>

        <button
          type="button"
          onClick={() => {
            setSearchInput('');
            setSearch('');
            changeWarehouse('');
          }}
          className="min-h-10 rounded-lg border border-slate-300 px-4 text-sm font-medium text-slate-700 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-emerald-600 focus:ring-offset-2"
        >
          Clear filters
        </button>
      </div>

      {warehouseError && (
        <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
          Could not load warehouse options: {warehouseError}
        </div>
      )}

      {error && (
        <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
          {error}
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th scope="col" className="px-4 py-3">Product</th>
                <th scope="col" className="px-4 py-3">SKU</th>
                <th scope="col" className="px-4 py-3">Warehouse</th>
                <th scope="col" className="px-4 py-3 text-right">On hand</th>
                <th scope="col" className="px-4 py-3 text-right">Reserved</th>
                <th scope="col" className="px-4 py-3 text-right">Available</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((row) => (
                <tr key={`${row.product_id}-${row.warehouse_id}`} className="hover:bg-slate-50/70">
                  <td className="px-4 py-3 font-medium text-slate-900">
                    {row.product_name}
                    <span className="ml-2 text-xs font-normal text-slate-500">
                      {row.unit_code}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-600">{row.product_sku}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                    {row.warehouse_name}
                    <span className="ml-2 text-xs text-slate-500">({row.warehouse_code})</span>
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-slate-700">
                    {Number(row.qty_on_hand).toLocaleString(undefined, { maximumFractionDigits: 3 })}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-slate-700">
                    {Number(row.qty_reserved).toLocaleString(undefined, { maximumFractionDigits: 3 })}
                  </td>
                  <td className="px-4 py-3 text-right font-semibold tabular-nums text-emerald-800">
                    {Number(row.available).toLocaleString(undefined, { maximumFractionDigits: 3 })}
                  </td>
                </tr>
              ))}
              {!loadingStock && rows.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-slate-500">
                    No stocked products found for these filters.
                  </td>
                </tr>
              )}
              {loadingStock && (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-slate-500" role="status">
                    Loading warehouse stock…
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <footer className="flex items-center justify-between border-t border-slate-200 px-4 py-3">
          <p className="text-xs text-slate-500">
            {rows.length ? `Showing ${offset + 1}–${offset + rows.length}` : 'No stock rows'}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={offset === 0 || loadingStock}
              onClick={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Previous
            </button>
            <button
              type="button"
              disabled={rows.length < PAGE_SIZE || loadingStock}
              onClick={() => setOffset((current) => current + PAGE_SIZE)}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </footer>
      </div>
    </section>
  );
}

export default function WarehouseStockPage() {
  return (
    <ProtectedPage>
      <WarehouseStockContent />
    </ProtectedPage>
  );
}
