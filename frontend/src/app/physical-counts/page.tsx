'use client';

import { useCallback, useEffect, useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { RequiredMark } from '@/components/forms/field-error';
import { SearchableSelect } from '@/components/forms/searchable-select';
import { useSessionProfile } from '@/components/auth/session-shell';
import { apiRequest } from '@/lib/auth-api';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';
import { physicalCountLinesSchema } from '@/lib/auth-validation';

type WarehouseOption = {
  id: number;
  code: string;
  name: string;
};

type PhysicalCountLine = {
  id: number;
  product_id: number;
  product_sku: string;
  product_name: string;
  unit_code: string;
  system_qty: string;
  counted_qty: string | null;
  variance_qty: string | null;
};

type PhysicalCount = {
  id: number;
  doc_no: string | null;
  count_date: string;
  warehouse_id: number;
  status: 'OPEN' | 'COUNTED' | 'POSTED';
  lines: PhysicalCountLine[];
};

type PhysicalCountListItem = Omit<PhysicalCount, 'lines'> & {
  total_lines: number;
  counted_lines: number;
};

const PAGE_SIZE = 50;

function today(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(
    now.getDate(),
  ).padStart(2, '0')}`;
}

function PhysicalCountsContent() {
  const profile = useSessionProfile();
  const canRead = profile?.permissions.includes('inventory.physical_counts.read') ?? false;
  const canCreate = profile?.permissions.includes('inventory.physical_counts.create') ?? false;
  const [warehouses, setWarehouses] = useState<WarehouseOption[]>([]);
  const [counts, setCounts] = useState<PhysicalCountListItem[]>([]);
  const [selectedCount, setSelectedCount] = useState<PhysicalCount | null>(null);
  const [countedQuantities, setCountedQuantities] = useState<Record<number, string>>({});
  const [warehouseId, setWarehouseId] = useState('');
  const [countDate, setCountDate] = useState(today);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const reloadCounts = useCallback(async (pageOffset: number) => {
    const params = new URLSearchParams({
      offset: String(pageOffset),
      limit: String(PAGE_SIZE),
    });
    setCounts(
      await apiRequest<PhysicalCountListItem[]>(
        `/api/v1/inventory/physical-counts?${params.toString()}`,
      ),
    );
  }, []);

  useEffect(() => {
    if (!canRead) return;
    let active = true;
    setLoading(true);
    Promise.all([
      apiRequest<WarehouseOption[]>('/api/v1/inventory/physical-counts/options'),
      apiRequest<PhysicalCountListItem[]>(
        `/api/v1/inventory/physical-counts?limit=${PAGE_SIZE}`,
      ),
    ])
      .then(([warehouseOptions, countList]) => {
        if (!active) return;
        setWarehouses(warehouseOptions);
        setCounts(countList);
      })
      .catch((cause: unknown) => {
        if (!active) return;
        const message = cause instanceof Error ? cause.message : 'Could not load physical counts';
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

  function selectCount(count: PhysicalCount) {
    setSelectedCount(count);
    setCountedQuantities(
      Object.fromEntries(
        count.lines.map((line) => [line.product_id, line.counted_qty ?? '']),
      ),
    );
    setError('');
  }

  async function loadCount(countId: number) {
    setError('');
    try {
      const count = await apiRequest<PhysicalCount>(
        `/api/v1/inventory/physical-counts/${countId}`,
      );
      selectCount(count);
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not load count sheet';
      setError(message);
      showErrorToast(message);
    }
  }

  async function startCount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setSaving(true);
    try {
      const count = await apiRequest<PhysicalCount>('/api/v1/inventory/physical-counts', {
        method: 'POST',
        body: JSON.stringify({
          count_date: countDate,
          warehouse_id: Number(warehouseId),
        }),
      });
      selectCount(count);
      setOffset(0);
      showSuccessToast('Physical count sheet started.');
      try {
        await reloadCounts(0);
      } catch (cause) {
        const message =
          cause instanceof Error ? cause.message : 'Count started, but the list refresh failed';
        setError(message);
        showErrorToast(message);
      }
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not start physical count';
      setError(message);
      showErrorToast(message);
    } finally {
      setSaving(false);
    }
  }

  async function saveCounts() {
    if (!selectedCount) return;
    const parsed = physicalCountLinesSchema.safeParse({
      lines: selectedCount.lines
        .filter((line) => countedQuantities[line.product_id] !== '')
        .map((line) => ({
          product_id: line.product_id,
          counted_qty: countedQuantities[line.product_id],
        })),
    });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? 'Check the counted quantities and try again.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const count = await apiRequest<PhysicalCount>(
        `/api/v1/inventory/physical-counts/${selectedCount.id}/lines`,
        { method: 'PUT', body: JSON.stringify(parsed.data) },
      );
      selectCount(count);
      showSuccessToast('Counted quantities saved.');
      try {
        await reloadCounts(offset);
      } catch (cause) {
        const message =
          cause instanceof Error ? cause.message : 'Quantities saved, but the list refresh failed';
        setError(message);
        showErrorToast(message);
      }
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not save counted quantities';
      setError(message);
      showErrorToast(message);
    } finally {
      setSaving(false);
    }
  }

  async function postCount() {
    if (!selectedCount) return;
    setSaving(true);
    setError('');
    try {
      const count = await apiRequest<PhysicalCount>(
        `/api/v1/inventory/physical-counts/${selectedCount.id}/post`,
        { method: 'POST' },
      );
      selectCount(count);
      showSuccessToast(`Physical count ${count.doc_no} posted.`);
      try {
        await reloadCounts(offset);
      } catch (cause) {
        const message =
          cause instanceof Error ? cause.message : 'Count posted, but the list refresh failed';
        setError(message);
        showErrorToast(message);
      }
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not post physical count';
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
      await reloadCounts(nextOffset);
      setOffset(nextOffset);
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not load physical counts';
      setError(message);
      showErrorToast(message);
    } finally {
      setLoading(false);
    }
  }

  if (!canRead) {
    return (
      <section className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
        Your account does not have permission to view physical counts.
      </section>
    );
  }

  const warehouseName = (id: number) =>
    warehouses.find((warehouse) => warehouse.id === id)?.name ?? `Warehouse ${id}`;

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Physical Count</h1>
        <p className="mt-1 text-sm text-slate-600">
          Snapshot current stock, enter counted quantities, review variances, and post the count.
          Posting is blocked if stock changed after the snapshot.
        </p>
      </header>

      {canCreate && (
        <form
          onSubmit={(event) => void startCount(event)}
          className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
        >
          <h2 className="text-lg font-semibold text-slate-900">Start a count sheet</h2>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="text-sm font-medium text-slate-700">
              Count date<RequiredMark />
              <input
                aria-label="Count date"
                required
                type="date"
                value={countDate}
                onChange={(event) => setCountDate(event.target.value)}
                className="mt-1.5 block min-h-10 w-full rounded-lg border border-slate-300 px-3 text-sm"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Warehouse<RequiredMark />
              <SearchableSelect
                aria-label="Warehouse"
                required
                placeholder="Search warehouse by name or code"
                value={warehouseId}
                onChange={setWarehouseId}
                options={warehouses.map((warehouse) => ({
                  value: String(warehouse.id),
                  label: `${warehouse.name} (${warehouse.code})`,
                  searchText: `${warehouse.name} ${warehouse.code}`,
                }))}
                className="mt-1.5 block min-h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm"
              />
            </label>
          </div>
          <button
            type="submit"
            disabled={saving || warehouses.length === 0}
            className="min-h-10 rounded-lg bg-emerald-700 px-4 text-sm font-semibold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {saving ? 'Starting…' : 'Start count'}
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

      {selectedCount && (
        <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <header className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">
                {selectedCount.doc_no ?? `Count sheet #${selectedCount.id}`}
              </h2>
              <p className="mt-1 text-sm text-slate-600">
                {selectedCount.count_date} · {warehouseName(selectedCount.warehouse_id)} ·{' '}
                {selectedCount.status}
              </p>
            </div>
            {canCreate && selectedCount.status === 'COUNTED' && (
              <button
                type="button"
                disabled={saving}
                onClick={() => void postCount()}
                className="min-h-10 rounded-lg bg-emerald-700 px-4 text-sm font-semibold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {saving ? 'Posting…' : 'Post count'}
              </button>
            )}
          </header>

          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">Product</th>
                  <th className="px-4 py-3 text-right">System quantity</th>
                  <th className="px-4 py-3">Counted quantity</th>
                  <th className="px-4 py-3 text-right">Variance</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {selectedCount.lines.map((line) => (
                  <tr key={line.id}>
                    <td className="px-4 py-3">
                      <span className="font-medium text-slate-900">{line.product_name}</span>
                      <span className="ml-2 text-xs text-slate-500">
                        {line.product_sku} · {line.unit_code}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">{line.system_qty}</td>
                    <td className="px-4 py-3">
                      <input
                        aria-label={`Counted quantity ${line.product_sku}`}
                        type="number"
                        min="0"
                        step="0.001"
                        disabled={!canCreate || selectedCount.status === 'POSTED' || saving}
                        value={countedQuantities[line.product_id] ?? ''}
                        onChange={(event) =>
                          setCountedQuantities((current) => ({
                            ...current,
                            [line.product_id]: event.target.value,
                          }))
                        }
                        className="min-h-9 w-36 rounded-lg border border-slate-300 px-3 text-sm disabled:bg-slate-100"
                      />
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {line.variance_qty ?? '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {canCreate && selectedCount.status !== 'POSTED' && (
            <button
              type="button"
              disabled={saving}
              onClick={() => void saveCounts()}
              className="min-h-10 rounded-lg border border-slate-300 px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? 'Saving…' : 'Save counted quantities'}
            </button>
          )}
        </section>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 px-5 py-4">
          <h2 className="font-semibold text-slate-900">Count sheets</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Document</th>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">Warehouse</th>
                <th className="px-4 py-3">Products counted</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {counts.map((count) => (
                <tr key={count.id}>
                  <td className="whitespace-nowrap px-4 py-3 font-medium text-slate-900">
                    {count.doc_no ?? `Count sheet #${count.id}`}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-600">{count.count_date}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                    {warehouseName(count.warehouse_id)}
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    {count.counted_lines}/{count.total_lines}
                  </td>
                  <td className="px-4 py-3">{count.status}</td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => void loadCount(count.id)}
                      className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
                    >
                      Open
                    </button>
                  </td>
                </tr>
              ))}
              {!loading && counts.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-slate-500">
                    No physical count sheets have been started.
                  </td>
                </tr>
              )}
              {loading && (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-slate-500" role="status">
                    Loading physical counts…
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <footer className="flex items-center justify-between border-t border-slate-200 px-4 py-3">
          <span className="text-xs text-slate-500">
            {counts.length ? `Showing ${offset + 1}–${offset + counts.length}` : 'No count sheets'}
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
              disabled={counts.length < PAGE_SIZE || loading}
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

export default function PhysicalCountsPage() {
  return (
    <ProtectedPage>
      <PhysicalCountsContent />
    </ProtectedPage>
  );
}
