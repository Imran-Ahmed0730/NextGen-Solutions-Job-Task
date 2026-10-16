'use client';

import { useCallback, useEffect, useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { RequiredMark } from '@/components/forms/field-error';
import { SearchableSelect } from '@/components/forms/searchable-select';
import { useSessionProfile } from '@/components/auth/session-shell';
import { apiRequest } from '@/lib/auth-api';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';
import { directPurchaseSchema } from '@/lib/auth-validation';

type SupplierOption = { id: number; code: string; name: string };
type WarehouseOption = { id: number; code: string; name: string };
type ProductOption = {
  id: number;
  sku: string;
  name: string;
  unit_code: string;
  allow_decimal: boolean;
};
type DirectPurchaseOptions = {
  suppliers: SupplierOption[];
  warehouses: WarehouseOption[];
  products: ProductOption[];
};
type DraftLine = { product_id: string; qty: string; unit_cost: string };
type DirectPurchaseLine = {
  id: number;
  product_id: number;
  product_sku: string;
  product_name: string;
  qty: string;
  unit_cost: string;
  line_total: string;
};
type DirectPurchase = {
  id: number;
  doc_no: string;
  doc_date: string;
  supplier_id: number;
  warehouse_id: number;
  status: string;
  total: string;
  paid_amount: string;
  money_account_id: number | null;
  note: string | null;
  lines: DirectPurchaseLine[];
};

const PAGE_SIZE = 50;

function today(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(
    now.getDate(),
  ).padStart(2, '0')}`;
}

function emptyLine(): DraftLine {
  return { product_id: '', qty: '', unit_cost: '' };
}

function DirectPurchasesContent() {
  const profile = useSessionProfile();
  const canRead = profile?.permissions.includes('purchase.direct_purchases.read') ?? false;
  const canCreate = profile?.permissions.includes('purchase.direct_purchases.create') ?? false;
  const [options, setOptions] = useState<DirectPurchaseOptions>({
    suppliers: [],
    warehouses: [],
    products: [],
  });
  const [purchases, setPurchases] = useState<DirectPurchase[]>([]);
  const [docDate, setDocDate] = useState(today);
  const [supplierId, setSupplierId] = useState('');
  const [warehouseId, setWarehouseId] = useState('');
  const [note, setNote] = useState('');
  const [lines, setLines] = useState<DraftLine[]>([emptyLine()]);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const reload = useCallback(async (nextOffset = 0) => {
    const [loadedOptions, loadedPurchases] = await Promise.all([
      apiRequest<DirectPurchaseOptions>('/api/v1/purchase/direct-purchases/options'),
      apiRequest<DirectPurchase[]>(
        `/api/v1/purchase/direct-purchases?offset=${nextOffset}&limit=${PAGE_SIZE + 1}`,
      ),
    ]);
    setOptions(loadedOptions);
    setPurchases(loadedPurchases.slice(0, PAGE_SIZE));
    setHasMore(loadedPurchases.length > PAGE_SIZE);
    setOffset(nextOffset);
  }, []);

  useEffect(() => {
    if (!canRead) return;
    let active = true;
    setLoading(true);
    reload()
      .catch((cause: unknown) => {
        if (!active) return;
        const message = cause instanceof Error ? cause.message : 'Could not load direct purchases';
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
    setSupplierId('');
    setWarehouseId('');
    setNote('');
    setLines([emptyLine()]);
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
    const parsed = directPurchaseSchema.safeParse({
      doc_date: docDate,
      supplier_id: Number(supplierId),
      warehouse_id: Number(warehouseId),
      note,
      lines: lines.map((line) => ({
        product_id: Number(line.product_id),
        qty: line.qty,
        unit_cost: line.unit_cost,
      })),
    });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? 'Check the direct purchase details.');
      return;
    }

    setError('');
    setSaving(true);
    try {
      const posted = await apiRequest<DirectPurchase>(
        '/api/v1/purchase/direct-purchases',
        {
          method: 'POST',
          body: JSON.stringify(parsed.data),
        },
      );
      showSuccessToast(`Direct purchase ${posted.doc_no} posted on credit.`);
      resetForm();
      try {
        await reload(0);
      } catch (cause) {
        const message =
          cause instanceof Error
            ? `Purchase posted, but the history could not be refreshed: ${cause.message}`
            : 'Purchase posted, but the history could not be refreshed.';
        setError(message);
        showErrorToast(message);
      }
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not post direct purchase';
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
      const message = cause instanceof Error ? cause.message : 'Could not load direct purchases';
      setError(message);
      showErrorToast(message);
    } finally {
      setLoading(false);
    }
  }

  if (!canRead) {
    return (
      <section className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
        Your account does not have permission to view direct purchases.
      </section>
    );
  }

  const supplierName = (id: number) =>
    options.suppliers.find((supplier) => supplier.id === id)?.name ?? `Supplier ${id}`;
  const warehouseName = (id: number) =>
    options.warehouses.find((warehouse) => warehouse.id === id)?.name ?? `Warehouse ${id}`;

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Direct Purchases</h1>
        <p className="mt-1 text-sm text-slate-600">
          Post a purchase without a purchase order. Purchases are recorded on supplier credit and
          can be paid from the Supplier Payments screen.
        </p>
      </header>

      {canCreate && (
        <form
          onSubmit={(event) => void submit(event)}
          className="space-y-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
        >
          <h2 className="text-lg font-semibold text-slate-900">Post direct purchase</h2>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="text-sm font-medium text-slate-700">
              Supplier<RequiredMark />
              <SearchableSelect
                aria-label="Supplier"
                required
                placeholder="Search supplier by code or name"
                value={supplierId}
                onChange={setSupplierId}
                options={options.suppliers.map((supplier) => ({
                  value: String(supplier.id),
                  label: `${supplier.code} — ${supplier.name}`,
                  searchText: `${supplier.code} ${supplier.name}`,
                }))}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Warehouse<RequiredMark />
              <SearchableSelect
                aria-label="Warehouse"
                required
                placeholder="Search warehouse by code or name"
                value={warehouseId}
                onChange={setWarehouseId}
                options={options.warehouses.map((warehouse) => ({
                  value: String(warehouse.id),
                  label: `${warehouse.code} — ${warehouse.name}`,
                  searchText: `${warehouse.code} ${warehouse.name}`,
                }))}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Purchase date<RequiredMark />
              <input
                aria-label="Purchase date"
                type="date"
                required
                value={docDate}
                onChange={(event) => setDocDate(event.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Note
              <input type="text"
                aria-label="Purchase note"
                maxLength={2000}
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder="Optional purchase note"
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
          </div>

          <div className="space-y-3">
            {lines.map((line, index) => {
              const product = options.products.find(
                (candidate) => String(candidate.id) === line.product_id,
              );
              return (
                <div
                  key={index}
                  className="grid gap-3 rounded-lg border border-slate-200 p-3 md:grid-cols-[2fr_1fr_1fr_auto]"
                >
                  <label className="text-sm font-medium text-slate-700">
                    Product<RequiredMark />
                    <SearchableSelect
                      aria-label={`Product ${index + 1}`}
                      required
                      placeholder="Search product by SKU or name"
                      value={line.product_id}
                      onChange={(value) => updateLine(index, 'product_id', value)}
                      options={options.products.map((option) => ({
                        value: String(option.id),
                        label: `${option.sku} — ${option.name}`,
                        searchText: `${option.sku} ${option.name}`,
                      }))}
                      className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
                    />
                    {product && (
                      <span className="mt-1 block text-xs text-slate-500">
                        Unit: {product.unit_code}
                      </span>
                    )}
                  </label>
                  <label className="text-sm font-medium text-slate-700">
                    Quantity<RequiredMark />
                    <input
                      aria-label={`Quantity ${index + 1}`}
                      type="number"
                      min="0"
                      step={product?.allow_decimal ? '0.001' : '1'}
                      required
                      value={line.qty}
                      onChange={(event) => updateLine(index, 'qty', event.target.value)}
                      placeholder="Enter quantity"
                      className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="text-sm font-medium text-slate-700">
                    Unit cost<RequiredMark />
                    <input
                      aria-label={`Unit cost ${index + 1}`}
                      type="number"
                      min="0"
                      step="0.0001"
                      required
                      value={line.unit_cost}
                      onChange={(event) => updateLine(index, 'unit_cost', event.target.value)}
                      placeholder="0.0000"
                      className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <button
                    type="button"
                    aria-label={`Remove product line ${index + 1}`}
                    disabled={lines.length === 1}
                    onClick={() =>
                      setLines((current) => current.filter((_, lineIndex) => lineIndex !== index))
                    }
                    className="self-center rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700 disabled:opacity-50"
                  >
                    Remove
                  </button>
                </div>
              );
            })}
          </div>

          {error && (
            <p role="alert" className="rounded-md bg-rose-50 p-3 text-sm text-rose-800">
              {error}
            </p>
          )}
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => setLines((current) => [...current, emptyLine()])}
              disabled={lines.length >= 500}
              className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 disabled:opacity-50"
            >
              Add product
            </button>
            <button
              type="submit"
              disabled={saving || options.products.length === 0}
              className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-800 disabled:opacity-60"
            >
              {saving ? 'Posting…' : 'Post purchase on credit'}
            </button>
          </div>
        </form>
      )}

      {error && !canCreate && (
        <p role="alert" className="rounded-md bg-rose-50 p-3 text-sm text-rose-800">
          {error}
        </p>
      )}

      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 px-5 py-4">
          <h2 className="font-semibold text-slate-900">Direct purchase history</h2>
        </div>
        {loading ? (
          <p className="p-5 text-sm text-slate-600">Loading direct purchases…</p>
        ) : purchases.length === 0 ? (
          <p className="p-5 text-sm text-slate-600">No direct purchases found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-600">
                <tr>
                  <th className="px-4 py-3">Purchase</th>
                  <th className="px-4 py-3">Date</th>
                  <th className="px-4 py-3">Supplier</th>
                  <th className="px-4 py-3">Warehouse</th>
                  <th className="px-4 py-3 text-right">Total</th>
                  <th className="px-4 py-3">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {purchases.map((purchase) => (
                  <tr key={purchase.id}>
                    <td className="px-4 py-3 font-medium text-slate-900">{purchase.doc_no}</td>
                    <td className="px-4 py-3">{purchase.doc_date}</td>
                    <td className="px-4 py-3">{supplierName(purchase.supplier_id)}</td>
                    <td className="px-4 py-3">{warehouseName(purchase.warehouse_id)}</td>
                    <td className="px-4 py-3 text-right">{purchase.total}</td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={() =>
                          setExpandedId((current) =>
                            current === purchase.id ? null : purchase.id,
                          )
                        }
                        className="font-medium text-emerald-800 hover:underline"
                      >
                        {expandedId === purchase.id ? 'Hide' : 'View'}
                      </button>
                    </td>
                  </tr>
                ))}
                {purchases.map(
                  (purchase) =>
                    expandedId === purchase.id && (
                      <tr key={`lines-${purchase.id}`}>
                        <td colSpan={6} className="bg-slate-50 px-6 py-4">
                          <ul className="space-y-1">
                            {purchase.lines.map((line) => (
                              <li key={line.id} className="flex flex-wrap justify-between gap-2">
                                <span>
                                  {line.product_sku} — {line.product_name} {line.qty} ×{' '}
                                  {line.unit_cost}
                                </span>
                                <span>{line.line_total}</span>
                              </li>
                            ))}
                          </ul>
                          {purchase.note && (
                            <p className="mt-2 text-slate-600">Note: {purchase.note}</p>
                          )}
                          <p className="mt-2 text-xs text-slate-500">
                            Recorded on credit; paid {purchase.paid_amount}.
                          </p>
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
              {purchases.length ? `${offset + 1}–${offset + purchases.length}` : '0'} purchases
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

export default function DirectPurchasesPage() {
  return (
    <ProtectedPage>
      <DirectPurchasesContent />
    </ProtectedPage>
  );
}
