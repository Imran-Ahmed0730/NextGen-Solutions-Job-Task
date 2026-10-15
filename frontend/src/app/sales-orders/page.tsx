'use client';

import { Fragment, useCallback, useEffect, useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { useSessionProfile } from '@/components/auth/session-shell';
import { FieldError, RequiredMark } from '@/components/forms/field-error';
import { SearchableSelect } from '@/components/forms/searchable-select';
import { apiRequest } from '@/lib/auth-api';
import {
  salesDeliverySchema,
  salesOrderReservationSchema,
  salesOrderSchema,
} from '@/lib/auth-validation';
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
type SalesOrderOptions = {
  customers: CustomerOption[];
  warehouses: WarehouseOption[];
  products: ProductOption[];
};
type DraftLine = { product_id: string; qty_ordered: string; unit_price: string };
type SalesOrderLine = DraftLine & {
  id: number;
  line_total: string;
  qty_reserved: string;
  qty_produced: string;
  qty_delivered: string;
  qty_available: string;
  qty_remaining: string;
  reservations: {
    id: number;
    qty: string;
    qty_consumed: string;
    qty_released: string;
    status: string;
  }[];
};
type SalesOrderRecord = {
  id: number;
  doc_no: string;
  doc_date: string;
  customer_id: number;
  quotation_id: number | null;
  warehouse_id: number;
  status: string;
  delivery_date: string | null;
  subtotal: string;
  discount: string;
  total: string;
  note: string | null;
  lines: SalesOrderLine[];
  deliveries: SalesDeliveryRecord[];
};
type SalesDeliveryRecord = {
  id: number;
  doc_no: string;
  doc_date: string;
  status: string;
  lines: {
    id: number;
    order_line_id: number;
    product_id: number;
    qty: string;
    unit_cost_cogs: string;
  }[];
};

const PAGE_SIZE = 50;
const emptyLine = (): DraftLine => ({ product_id: '', qty_ordered: '', unit_price: '' });

function today(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(
    now.getDate(),
  ).padStart(2, '0')}`;
}

function SalesOrdersContent() {
  const profile = useSessionProfile();
  const canRead = profile?.permissions.includes('sales.orders.read') ?? false;
  const canCreate = profile?.permissions.includes('sales.orders.create') ?? false;
  const canUpdate = profile?.permissions.includes('sales.orders.update') ?? false;
  const canReserve = profile?.permissions.includes('sales.orders.reserve') ?? false;
  const canDeliver = profile?.permissions.includes('sales.deliveries.create') ?? false;
  const [options, setOptions] = useState<SalesOrderOptions>({
    customers: [],
    warehouses: [],
    products: [],
  });
  const [orders, setOrders] = useState<SalesOrderRecord[]>([]);
  const [docDate, setDocDate] = useState(today);
  const [customerId, setCustomerId] = useState('');
  const [warehouseId, setWarehouseId] = useState('');
  const [deliveryDate, setDeliveryDate] = useState('');
  const [discount, setDiscount] = useState('0.00');
  const [note, setNote] = useState('');
  const [lines, setLines] = useState<DraftLine[]>([emptyLine()]);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [detailsId, setDetailsId] = useState<number | null>(null);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [reservationQuantities, setReservationQuantities] = useState<Record<number, string>>({});
  const [reservationBusy, setReservationBusy] = useState(false);
  const [deliveryQuantities, setDeliveryQuantities] = useState<Record<number, string>>({});
  const [deliveryDates, setDeliveryDates] = useState<Record<number, string>>({});
  const [deliveryBusy, setDeliveryBusy] = useState(false);
  const [error, setError] = useState('');

  const reload = useCallback(async (nextOffset = 0) => {
    const [loadedOptions, loadedOrders] = await Promise.all([
      apiRequest<SalesOrderOptions>('/api/v1/sales/orders/options'),
      apiRequest<SalesOrderRecord[]>(
        `/api/v1/sales/orders?offset=${nextOffset}&limit=${PAGE_SIZE + 1}`,
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
        const message = cause instanceof Error ? cause.message : 'Could not load sales orders';
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
    setWarehouseId('');
    setDeliveryDate('');
    setDiscount('0.00');
    setNote('');
    setLines([emptyLine()]);
    setEditingId(null);
    setError('');
  }

  function editOrder(order: SalesOrderRecord) {
    setEditingId(order.id);
    setDocDate(order.doc_date);
    setCustomerId(String(order.customer_id));
    setWarehouseId(String(order.warehouse_id));
    setDeliveryDate(order.delivery_date ?? '');
    setDiscount(order.discount);
    setNote(order.note ?? '');
    setLines(
      order.lines.map((line) => ({
        product_id: String(line.product_id),
        qty_ordered: line.qty_ordered,
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
    const parsed = salesOrderSchema.safeParse({
      doc_date: docDate,
      customer_id: Number(customerId),
      warehouse_id: Number(warehouseId),
      delivery_date: deliveryDate,
      discount,
      note,
      lines: lines.map((line) => ({
        product_id: Number(line.product_id),
        qty_ordered: line.qty_ordered,
        unit_price: line.unit_price,
      })),
    });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? 'Check the sales order details.');
      return;
    }

    setSaving(true);
    setError('');
    try {
      const saved = await apiRequest<SalesOrderRecord>(
        editingId ? `/api/v1/sales/orders/${editingId}` : '/api/v1/sales/orders',
        { method: editingId ? 'PUT' : 'POST', body: JSON.stringify(parsed.data) },
      );
      showSuccessToast(`Sales order ${saved.doc_no} ${editingId ? 'updated' : 'created'}.`);
      resetForm();
      try {
        await reload(0);
      } catch (cause) {
        const message =
          cause instanceof Error
            ? `Sales order saved, but history could not be refreshed: ${cause.message}`
            : 'Sales order saved, but history could not be refreshed.';
        setError(message);
        showErrorToast(message);
      }
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not save sales order';
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
      const message = cause instanceof Error ? cause.message : 'Could not load sales orders';
      setError(message);
      showErrorToast(message);
    } finally {
      setLoading(false);
    }
  }

  function replaceOrder(updated: SalesOrderRecord) {
    setOrders((current) => current.map((order) => (order.id === updated.id ? updated : order)));
  }

  async function reserveLine(orderId: number, lineId: number) {
    const parsed = salesOrderReservationSchema.safeParse({
      qty: reservationQuantities[lineId] ?? '',
    });
    if (!parsed.success) {
      const message = parsed.error.issues[0]?.message ?? 'Enter a valid reservation quantity.';
      setError(message);
      showErrorToast(message);
      return;
    }
    const order = orders.find((item) => item.id === orderId);
    const line = order?.lines.find((item) => item.id === lineId);
    const product = options.products.find((item) => item.id === Number(line?.product_id));
    if (product && !product.allow_decimal && !/^\d+(?:\.0+)?$/.test(parsed.data.qty)) {
      const message = `${product.unit_code} quantities must be whole numbers.`;
      setError(message);
      showErrorToast(message);
      return;
    }
    setReservationBusy(true);
    setError('');
    try {
      const updated = await apiRequest<SalesOrderRecord>(
        `/api/v1/sales/orders/${orderId}/lines/${lineId}/reservations`,
        { method: 'POST', body: JSON.stringify(parsed.data) },
      );
      replaceOrder(updated);
      setReservationQuantities((current) => ({ ...current, [lineId]: '' }));
      showSuccessToast('Stock reserved for the sales order.');
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not reserve stock';
      setError(message);
      showErrorToast(message);
    } finally {
      setReservationBusy(false);
    }
  }

  async function releaseReservation(orderId: number, reservationId: number) {
    setReservationBusy(true);
    setError('');
    try {
      const updated = await apiRequest<SalesOrderRecord>(
        `/api/v1/sales/orders/${orderId}/reservations/${reservationId}`,
        { method: 'DELETE' },
      );
      replaceOrder(updated);
      showSuccessToast('Reserved stock released.');
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not release reserved stock';
      setError(message);
      showErrorToast(message);
    } finally {
      setReservationBusy(false);
    }
  }

  async function deliverOrder(order: SalesOrderRecord) {
    const parsed = salesDeliverySchema.safeParse({
      doc_date: deliveryDates[order.id] ?? today(),
      lines: order.lines.flatMap((line) => {
        const qty = deliveryQuantities[line.id] ?? '';
        return qty.trim() ? [{ order_line_id: line.id, qty }] : [];
      }),
    });
    if (!parsed.success) {
      const message = parsed.error.issues[0]?.message ?? 'Check the delivery details.';
      setError(message);
      showErrorToast(message);
      return;
    }
    for (const deliveryLine of parsed.data.lines) {
      const orderLine = order.lines.find((line) => line.id === deliveryLine.order_line_id);
      if (!orderLine || Number(deliveryLine.qty) > Number(orderLine.qty_ordered) - Number(orderLine.qty_delivered)) {
        const message = 'A delivery quantity cannot exceed the remaining ordered quantity.';
        setError(message);
        showErrorToast(message);
        return;
      }
      const product = options.products.find((item) => item.id === Number(orderLine.product_id));
      if (product && !product.allow_decimal && !/^\d+(?:\.0+)?$/.test(deliveryLine.qty)) {
        const message = `${product.unit_code} quantities must be whole numbers.`;
        setError(message);
        showErrorToast(message);
        return;
      }
    }

    setDeliveryBusy(true);
    setError('');
    try {
      const delivery = await apiRequest<SalesDeliveryRecord>(
        `/api/v1/sales/orders/${order.id}/deliveries`,
        { method: 'POST', body: JSON.stringify(parsed.data) },
      );
      showSuccessToast(`Delivery ${delivery.doc_no} posted.`);
      setDeliveryQuantities((current) => ({
        ...current,
        ...Object.fromEntries(order.lines.map((line) => [line.id, ''])),
      }));
      try {
        await reload(offset);
      } catch (cause) {
        const message =
          cause instanceof Error
            ? `Delivery posted, but order history could not be refreshed: ${cause.message}`
            : 'Delivery posted, but order history could not be refreshed.';
        setError(message);
        showErrorToast(message);
      }
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not post delivery';
      setError(message);
      showErrorToast(message);
    } finally {
      setDeliveryBusy(false);
    }
  }

  if (!canRead) {
    return (
      <section className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
        Your account does not have permission to view sales orders.
      </section>
    );
  }

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Sales Orders</h1>
        <p className="mt-1 text-sm text-slate-600">
          Create and update draft sales orders, then reserve or release stock through the inventory
          reservation service.
        </p>
      </header>

      {(canCreate || (editingId !== null && canUpdate)) && (
        <form onSubmit={submit} className="space-y-5 rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-lg font-semibold text-slate-900">
            {editingId ? 'Edit Draft Sales Order' : 'New Sales Order'}
          </h2>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-1 text-sm font-medium text-slate-700">
              <span>Order date <RequiredMark /></span>
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
                options={options.customers.map((item) => ({
                  value: String(item.id),
                  label: `${item.code} - ${item.name}`,
                }))}
                placeholder="Search or select a customer"
              />
            </label>
            <label className="space-y-1 text-sm font-medium text-slate-700">
              <span>Warehouse <RequiredMark /></span>
              <SearchableSelect
                required
                aria-label="Warehouse"
                value={warehouseId}
                onChange={setWarehouseId}
                options={options.warehouses.map((item) => ({
                  value: String(item.id),
                  label: `${item.code} - ${item.name}`,
                }))}
                placeholder="Search or select a warehouse"
              />
            </label>
            <label className="space-y-1 text-sm font-medium text-slate-700">
              Delivery date
              <input
                type="date"
                value={deliveryDate}
                onChange={(event) => setDeliveryDate(event.target.value)}
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
              Order lines <RequiredMark />
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
                    options={options.products.map((item) => ({
                      value: String(item.id),
                      label: `${item.sku} - ${item.name}`,
                    }))}
                    placeholder="Search or select product"
                  />
                </label>
                <label className="space-y-1 text-sm text-slate-700">
                  Quantity <RequiredMark />
                  <input
                    required
                    inputMode="decimal"
                    aria-label={`Quantity ${index + 1}`}
                    value={line.qty_ordered}
                    onChange={(event) => updateLine(index, 'qty_ordered', event.target.value)}
                    placeholder="Enter quantity"
                    className="min-h-10 w-full rounded-lg border border-slate-300 bg-white px-3"
                  />
                </label>
                <label className="space-y-1 text-sm text-slate-700">
                  Unit price <RequiredMark />
                  <input
                    required
                    inputMode="decimal"
                    aria-label={`Unit price ${index + 1}`}
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
              placeholder="Optional sales order note"
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
            />
          </label>
          {error && <FieldError id="sales-order-error" message={error} />}
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

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-5 py-4">
          <h2 className="font-semibold text-slate-900">Sales Order History</h2>
        </div>
        {loading ? (
          <p className="p-5 text-sm text-slate-600">Loading sales orders…</p>
        ) : orders.length === 0 ? (
          <p className="p-5 text-sm text-slate-600">No sales orders found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-slate-600">
                <tr>
                  <th className="px-4 py-3">Document</th>
                  <th className="px-4 py-3">Date</th>
                  <th className="px-4 py-3">Customer</th>
                  <th className="px-4 py-3">Warehouse</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Total</th>
                  <th className="px-4 py-3">Details</th>
                  {(canUpdate || canReserve || canDeliver) && <th className="px-4 py-3">Action</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {orders.map((order) => (
                  <Fragment key={order.id}>
                    <tr>
                      <td className="px-4 py-3 font-medium text-slate-900">{order.doc_no}</td>
                      <td className="px-4 py-3">{order.doc_date}</td>
                      <td className="px-4 py-3">
                        {options.customers.find((item) => item.id === order.customer_id)?.name ??
                          `Customer ${order.customer_id}`}
                      </td>
                      <td className="px-4 py-3">
                        {options.warehouses.find((item) => item.id === order.warehouse_id)?.name ??
                          `Warehouse ${order.warehouse_id}`}
                      </td>
                      <td className="px-4 py-3">{order.status}</td>
                      <td className="px-4 py-3 text-right">{order.total}</td>
                      <td className="px-4 py-3">
                        <button
                          type="button"
                          onClick={() =>
                            setDetailsId((current) => (current === order.id ? null : order.id))
                          }
                          className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-700"
                        >
                          {detailsId === order.id ? 'Hide' : 'View'}
                        </button>
                      </td>
                      {(canUpdate || canReserve || canDeliver) && (
                        <td className="px-4 py-3">
                          {canUpdate &&
                            order.status === 'DRAFT' &&
                            order.lines.every((line) => line.reservations.length === 0) && (
                            <button
                              type="button"
                              onClick={() => editOrder(order)}
                              className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-700"
                            >
                              Edit
                            </button>
                          )}
                        </td>
                      )}
                    </tr>
                    {detailsId === order.id && (
                      <tr key={`${order.id}-details`}>
                        <td
                          colSpan={canUpdate || canReserve || canDeliver ? 8 : 7}
                          className="bg-slate-50 px-5 py-3"
                        >
                          <p className="mb-2 text-xs text-slate-600">
                            Ordered / Available stock / Reserved / Produced / Delivered / Remaining
                          </p>
                          <ul className="space-y-1 text-sm">
                            {order.lines.map((line) => (
                              <li key={line.id} className="space-y-2 py-2">
                                {options.products.find((item) => item.id === Number(line.product_id))
                                  ?.name ?? `Product ${line.product_id}`}
                                : {line.qty_ordered} / {line.qty_available} / {line.qty_reserved} /{' '}
                                {line.qty_produced} / {line.qty_delivered} / {line.qty_remaining} ·{' '}
                                {line.line_total}
                                {canReserve && order.status === 'DRAFT' && (
                                  <div className="flex flex-wrap items-center gap-2">
                                    <label className="text-xs text-slate-600">
                                      Reserve quantity <RequiredMark />
                                      <input
                                        required
                                        aria-label={`Reserve quantity for line ${line.id}`}
                                        inputMode="decimal"
                                        value={reservationQuantities[line.id] ?? ''}
                                        placeholder="Enter quantity"
                                        onChange={(event) =>
                                          setReservationQuantities((current) => ({
                                            ...current,
                                            [line.id]: event.target.value,
                                          }))
                                        }
                                        className="ml-2 min-h-8 w-28 rounded-md border border-slate-300 bg-white px-2"
                                      />
                                    </label>
                                    <button
                                      type="button"
                                      disabled={reservationBusy}
                                      onClick={() => void reserveLine(order.id, line.id)}
                                      className="rounded-md border border-emerald-700 px-2 py-1 text-xs text-emerald-800 disabled:opacity-50"
                                    >
                                      Reserve
                                    </button>
                                  </div>
                                )}
                                {line.reservations.map((reservation) => (
                                  <div
                                    key={reservation.id}
                                    className="flex flex-wrap items-center gap-2 text-xs text-slate-600"
                                  >
                                    Reservation {reservation.id}: {reservation.status} · qty{' '}
                                    {reservation.qty}, consumed {reservation.qty_consumed}, released{' '}
                                    {reservation.qty_released}
                                    {canReserve && reservation.status === 'ACTIVE' && (
                                      <button
                                        type="button"
                                        disabled={reservationBusy}
                                        onClick={() =>
                                          void releaseReservation(order.id, reservation.id)
                                        }
                                        className="rounded-md border border-amber-700 px-2 py-1 text-amber-800 disabled:opacity-50"
                                      >
                                        Release remaining
                                      </button>
                                    )}
                                  </div>
                                ))}
                              </li>
                            ))}
                          </ul>
                          {canDeliver &&
                            order.status === 'DRAFT' &&
                            order.lines.some((line) => Number(line.qty_delivered) < Number(line.qty_ordered)) && (
                              <div className="mt-4 space-y-3 border-t border-slate-200 pt-4">
                                <h3 className="text-sm font-semibold text-slate-800">
                                  Post Delivery · Delivery quantities <RequiredMark />
                                </h3>
                                <label className="block max-w-xs text-xs font-medium text-slate-600">
                                  Delivery date <RequiredMark />
                                  <input
                                    aria-label={`Delivery date for ${order.doc_no}`}
                                    type="date"
                                    required
                                    value={deliveryDates[order.id] ?? today()}
                                    onChange={(event) =>
                                      setDeliveryDates((current) => ({
                                        ...current,
                                        [order.id]: event.target.value,
                                      }))
                                    }
                                    className="mt-1 min-h-9 w-full rounded-md border border-slate-300 bg-white px-2"
                                  />
                                </label>
                                <div className="grid gap-2 sm:grid-cols-2">
                                  {order.lines
                                    .filter(
                                      (line) =>
                                        Number(line.qty_delivered) < Number(line.qty_ordered),
                                    )
                                    .map((line, index) => (
                                      <label
                                        key={`delivery-${line.id}`}
                                        className="text-xs font-medium text-slate-600"
                                      >
                                        Delivery quantity for line {index + 1}
                                        <input
                                          aria-label={`Delivery quantity for line ${line.id}`}
                                          inputMode="decimal"
                                          value={deliveryQuantities[line.id] ?? ''}
                                          placeholder="Enter quantity"
                                          onChange={(event) =>
                                            setDeliveryQuantities((current) => ({
                                              ...current,
                                              [line.id]: event.target.value,
                                            }))
                                          }
                                          className="mt-1 min-h-9 w-full rounded-md border border-slate-300 bg-white px-2"
                                        />
                                      </label>
                                    ))}
                                </div>
                                <button
                                  type="button"
                                  disabled={deliveryBusy}
                                  onClick={() => void deliverOrder(order)}
                                  className="rounded-md border border-emerald-700 px-3 py-1.5 text-xs text-emerald-800 disabled:opacity-50"
                                >
                                  {deliveryBusy ? 'Posting…' : 'Post delivery'}
                                </button>
                              </div>
                            )}
                          {order.deliveries.length > 0 && (
                            <div className="mt-4 border-t border-slate-200 pt-4">
                              <h3 className="text-sm font-semibold text-slate-800">Delivery history</h3>
                              <ul className="mt-2 space-y-2 text-xs text-slate-600">
                                {order.deliveries.map((delivery) => (
                                  <li key={delivery.id}>
                                    <p className="font-medium text-slate-800">
                                      {delivery.doc_no} · {delivery.doc_date} · {delivery.status}
                                    </p>
                                    {delivery.lines.map((line) => (
                                      <p key={line.id}>
                                        {options.products.find((item) => item.id === line.product_id)?.name ??
                                          `Product ${line.product_id}`}
                                        : delivered {line.qty} · COGS/unit {line.unit_cost_cogs}
                                      </p>
                                    ))}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
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

export default function SalesOrdersPage() {
  return (
    <ProtectedPage>
      <SalesOrdersContent />
    </ProtectedPage>
  );
}
