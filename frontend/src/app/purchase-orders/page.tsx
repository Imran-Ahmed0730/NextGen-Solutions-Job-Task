'use client';

import { useCallback, useEffect, useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { RequiredMark } from '@/components/forms/field-error';
import { SearchableSelect } from '@/components/forms/searchable-select';
import { useSessionProfile } from '@/components/auth/session-shell';
import { apiRequest } from '@/lib/auth-api';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';
import { purchaseOrderSchema } from '@/lib/auth-validation';

type SupplierOption = { id: number; code: string; name: string };
type WarehouseOption = { id: number; code: string; name: string };
type ProductOption = {
  id: number;
  sku: string;
  name: string;
  unit_code: string;
  allow_decimal: boolean;
};
type PurchaseOrderOptions = {
  suppliers: SupplierOption[];
  warehouses: WarehouseOption[];
  products: ProductOption[];
};
type PurchaseOrderLine = {
  id: number;
  product_id: number;
  qty: string;
  unit_price: string;
  line_total: string;
  received_qty: string;
};
type PurchaseOrder = {
  id: number;
  doc_no: string;
  doc_date: string;
  supplier_id: number;
  warehouse_id: number;
  status: string;
  expected_date: string | null;
  subtotal: string;
  discount: string;
  total: string;
  note: string | null;
  lines: PurchaseOrderLine[];
};
type DraftLine = { product_id: string; qty: string; unit_price: string };

const PAGE_SIZE = 50;

function today(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(
    now.getDate(),
  ).padStart(2, '0')}`;
}

function emptyLine(): DraftLine {
  return { product_id: '', qty: '', unit_price: '' };
}

function PurchaseOrdersContent() {
  const profile = useSessionProfile();
  const canRead = profile?.permissions.includes('purchase.orders.read') ?? false;
  const canCreate = profile?.permissions.includes('purchase.orders.create') ?? false;
  const canUpdate = profile?.permissions.includes('purchase.orders.update') ?? false;
  const [options, setOptions] = useState<PurchaseOrderOptions>({
    suppliers: [],
    warehouses: [],
    products: [],
  });
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [editing, setEditing] = useState<PurchaseOrder | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [docDate, setDocDate] = useState(today);
  const [supplierId, setSupplierId] = useState('');
  const [warehouseId, setWarehouseId] = useState('');
  const [expectedDate, setExpectedDate] = useState('');
  const [discount, setDiscount] = useState('0.00');
  const [note, setNote] = useState('');
  const [lines, setLines] = useState<DraftLine[]>([emptyLine()]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const reload = useCallback(async (nextOffset = 0) => {
    const [loadedOptions, loadedOrders] = await Promise.all([
      apiRequest<PurchaseOrderOptions>('/api/v1/purchase/orders/options'),
      apiRequest<PurchaseOrder[]>(
        `/api/v1/purchase/orders?offset=${nextOffset}&limit=${PAGE_SIZE + 1}`,
      ),
    ]);
    setOptions(loadedOptions);
    setOrders(loadedOrders.slice(0, PAGE_SIZE));
    setHasMore(loadedOrders.length > PAGE_SIZE);
    setOffset(nextOffset);
  }, []);

  useEffect(() => {
    if (!canRead) return;
    let active = true;
    setLoading(true);
    reload()
      .catch((cause: unknown) => {
        if (!active) return;
        const message = cause instanceof Error ? cause.message : 'Could not load purchase orders';
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
    setEditing(null);
    setDocDate(today());
    setSupplierId('');
    setWarehouseId('');
    setExpectedDate('');
    setDiscount('0.00');
    setNote('');
    setLines([emptyLine()]);
    setError('');
  }

  function startEditing(order: PurchaseOrder) {
    setEditing(order);
    setDocDate(order.doc_date);
    setSupplierId(String(order.supplier_id));
    setWarehouseId(String(order.warehouse_id));
    setExpectedDate(order.expected_date ?? '');
    setDiscount(order.discount);
    setNote(order.note ?? '');
    setLines(
      order.lines.map((line) => ({
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
    const parsed = purchaseOrderSchema.safeParse({
      doc_date: docDate,
      supplier_id: Number(supplierId),
      warehouse_id: Number(warehouseId),
      expected_date: expectedDate,
      discount,
      note,
      lines: lines.map((line) => ({
        product_id: Number(line.product_id),
        qty: line.qty,
        unit_price: line.unit_price,
      })),
    });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? 'Check the purchase order details.');
      return;
    }

    setError('');
    setSaving(true);
    try {
      const saved = await apiRequest<PurchaseOrder>(
        editing ? `/api/v1/purchase/orders/${editing.id}` : '/api/v1/purchase/orders',
        {
          method: editing ? 'PUT' : 'POST',
          body: JSON.stringify(parsed.data),
        },
      );
      showSuccessToast(`Purchase order ${saved.doc_no} saved as a draft.`);
      resetForm();
      try {
        await reload(0);
      } catch (cause) {
        const message =
          cause instanceof Error
            ? `Purchase order saved, but the list could not be refreshed: ${cause.message}`
            : 'Purchase order saved, but the list could not be refreshed.';
        setError(message);
        showErrorToast(message);
      }
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not save purchase order';
      setError(message);
      showErrorToast(message);
    } finally {
      setSaving(false);
    }
  }

  if (!canRead) {
    return (
      <section className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
        Your account does not have permission to view purchase orders.
      </section>
    );
  }

  const supplierName = (id: number) =>
    options.suppliers.find((supplier) => supplier.id === id)?.name ?? `Supplier ${id}`;
  const warehouseName = (id: number) =>
    options.warehouses.find((warehouse) => warehouse.id === id)?.name ?? `Warehouse ${id}`;
  const productName = (id: number) =>
    options.products.find((product) => product.id === id)?.name ?? `Product ${id}`;

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Purchase Orders</h1>
        <p className="mt-1 text-sm text-slate-600">
          Create and update purchase order drafts. Drafts do not post stock or supplier dues.
        </p>
      </header>

      {(editing ? canUpdate : canCreate) && (
        <form
          onSubmit={(event) => void submit(event)}
          className="space-y-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-slate-900">
              {editing ? `Edit draft ${editing.doc_no}` : 'New purchase order draft'}
            </h2>
            {editing && (
              <button
                type="button"
                onClick={resetForm}
                className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Cancel editing
              </button>
            )}
          </div>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <label className="text-sm font-medium text-slate-700">
              Document date<RequiredMark />
              <input
                aria-label="Document date"
                type="date"
                required
                value={docDate}
                onChange={(event) => setDocDate(event.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
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
              Expected date
              <input
                aria-label="Expected date"
                type="date"
                value={expectedDate}
                onChange={(event) => setExpectedDate(event.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Discount
              <input
                aria-label="Discount"
                type="number"
                min="0"
                step="0.01"
                value={discount}
                onChange={(event) => setDiscount(event.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
            <label className="text-sm font-medium text-slate-700 lg:col-span-1">
              Note
              <input
                aria-label="Note"
                maxLength={2000}
                value={note}
                onChange={(event) => setNote(event.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <h3 className="font-semibold text-slate-900">Products</h3>
              <button
                type="button"
                onClick={() => setLines((current) => [...current, emptyLine()])}
                disabled={lines.length >= 500}
                className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                Add product
              </button>
            </div>
            {lines.map((line, index) => {
              const selectedProduct = options.products.find(
                (product) => String(product.id) === line.product_id,
              );
              return (
                <div
                  key={index}
                  className="grid gap-3 rounded-lg border border-slate-200 p-3 md:grid-cols-[2fr_1fr_1fr_auto]"
                >
                  <label className="text-sm font-medium text-slate-700">
                    Product {index + 1}<RequiredMark />
                    <SearchableSelect
                      aria-label={`Product ${index + 1}`}
                      required
                      placeholder="Search product by SKU or name"
                      value={line.product_id}
                      onChange={(value) => updateLine(index, 'product_id', value)}
                      options={options.products.map((product) => ({
                        value: String(product.id),
                        label: `${product.sku} — ${product.name}`,
                        searchText: `${product.sku} ${product.name}`,
                      }))}
                      className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="text-sm font-medium text-slate-700">
                    Quantity {selectedProduct ? `(${selectedProduct.unit_code})` : ''}
                    <RequiredMark />
                    <input
                      aria-label={`Quantity ${index + 1}`}
                      type="number"
                      min="0"
                      step={selectedProduct?.allow_decimal ? '0.001' : '1'}
                      required
                      value={line.qty}
                      onChange={(event) => updateLine(index, 'qty', event.target.value)}
                      className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="text-sm font-medium text-slate-700">
                    Unit price<RequiredMark />
                    <input
                      aria-label={`Unit price ${index + 1}`}
                      type="number"
                      min="0"
                      step="0.01"
                      required
                      value={line.unit_price}
                      onChange={(event) => updateLine(index, 'unit_price', event.target.value)}
                      className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <button
                    type="button"
                    onClick={() =>
                      setLines((current) => current.filter((_, lineIndex) => lineIndex !== index))
                    }
                    disabled={lines.length === 1}
                    aria-label={`Remove product ${index + 1}`}
                    className="self-end rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
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
          <button
            type="submit"
            disabled={saving}
            className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-800 disabled:opacity-60"
          >
            {saving ? 'Saving…' : 'Save draft'}
          </button>
        </form>
      )}

      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 px-5 py-4">
          <h2 className="font-semibold text-slate-900">Purchase order history</h2>
        </div>
        {loading ? (
          <p className="p-5 text-sm text-slate-600">Loading purchase orders…</p>
        ) : orders.length === 0 ? (
          <p className="p-5 text-sm text-slate-600">No purchase orders found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-600">
                <tr>
                  <th className="px-4 py-3">Document</th>
                  <th className="px-4 py-3">Date</th>
                  <th className="px-4 py-3">Supplier</th>
                  <th className="px-4 py-3">Warehouse</th>
                  <th className="px-4 py-3 text-right">Total</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {orders.map((order) => (
                  <tr key={order.id}>
                    <td className="px-4 py-3 font-medium text-slate-900">{order.doc_no}</td>
                    <td className="px-4 py-3">{order.doc_date}</td>
                    <td className="px-4 py-3">{supplierName(order.supplier_id)}</td>
                    <td className="px-4 py-3">{warehouseName(order.warehouse_id)}</td>
                    <td className="px-4 py-3 text-right">{order.total}</td>
                    <td className="px-4 py-3">{order.status}</td>
                    <td className="space-x-3 whitespace-nowrap px-4 py-3">
                      <button
                        type="button"
                        onClick={() =>
                          setExpandedId((current) => (current === order.id ? null : order.id))
                        }
                        className="font-medium text-emerald-800 hover:underline"
                      >
                        {expandedId === order.id ? 'Hide lines' : 'View lines'}
                      </button>
                      {order.status === 'DRAFT' && canUpdate && (
                        <button
                          type="button"
                          onClick={() => startEditing(order)}
                          className="font-medium text-emerald-800 hover:underline"
                        >
                          Edit draft
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {orders.map(
                  (order) =>
                    expandedId === order.id && (
                      <tr key={`lines-${order.id}`}>
                        <td colSpan={7} className="bg-slate-50 px-6 py-4">
                          <ul className="space-y-1">
                            {order.lines.map((line) => (
                              <li key={line.id} className="flex flex-wrap justify-between gap-2">
                                <span>
                                  {productName(line.product_id)} — {line.qty} × {line.unit_price}
                                  {Number(line.received_qty) > 0 &&
                                    ` · received ${line.received_qty}`}
                                </span>
                                <span>{line.line_total}</span>
                              </li>
                            ))}
                            <li className="border-t border-slate-200 pt-2 text-right font-medium">
                              Subtotal {order.subtotal} · Discount {order.discount} · Total{' '}
                              {order.total}
                            </li>
                          </ul>
                          {order.note && <p className="mt-2 text-slate-600">Note: {order.note}</p>}
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
              onClick={() => {
                setLoading(true);
                setError('');
                void reload(Math.max(offset - PAGE_SIZE, 0))
                  .catch((cause: unknown) => {
                    const message =
                      cause instanceof Error ? cause.message : 'Could not load purchase orders';
                    setError(message);
                    showErrorToast(message);
                  })
                  .finally(() => setLoading(false));
              }}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 disabled:opacity-50"
            >
              Previous
            </button>
            <span className="text-xs text-slate-500">
              {orders.length ? `${offset + 1}–${offset + orders.length}` : '0'} purchase orders
            </span>
            <button
              type="button"
              disabled={!hasMore}
              onClick={() => {
                setLoading(true);
                setError('');
                void reload(offset + PAGE_SIZE)
                  .catch((cause: unknown) => {
                    const message =
                      cause instanceof Error ? cause.message : 'Could not load purchase orders';
                    setError(message);
                    showErrorToast(message);
                  })
                  .finally(() => setLoading(false));
              }}
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

export default function PurchaseOrdersPage() {
  return (
    <ProtectedPage>
      <PurchaseOrdersContent />
    </ProtectedPage>
  );
}
