'use client';

import { useCallback, useEffect, useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { useSessionProfile } from '@/components/auth/session-shell';
import { FieldError, RequiredMark } from '@/components/forms/field-error';
import { SearchableSelect } from '@/components/forms/searchable-select';
import { IconActionButton } from '@/components/ui/action-icon';
import { apiRequest } from '@/lib/auth-api';
import { statusLabel } from '@/lib/display-labels';
import {
  productionOrderCompleteSchema,
  productionOrderSchema,
} from '@/lib/auth-validation';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';

type ProductionBOMOption = {
  id: number;
  code: string;
  finished_product_id: number;
  output_qty: string;
  labor_cost_default: string;
  overhead_cost_default: string;
};
type SalesOrderLineOption = {
  id: number;
  sales_order_id: number;
  doc_no: string;
  product_id: number;
  product_sku: string;
  product_name: string;
  warehouse_id: number;
  qty_ordered: string;
  qty_reserved: string;
  qty_produced: string;
  qty_delivered: string;
};
type WarehouseOption = { id: number; code: string; name: string };
type ProductionOptions = {
  boms: ProductionBOMOption[];
  warehouses: WarehouseOption[];
  sales_order_lines: SalesOrderLineOption[];
};
type ConsumptionLine = {
  id: number;
  product_id: number;
  qty: string;
  unit_cost: string;
  line_cost: string;
};
type OutputLine = { id: number; product_id: number; qty: string; unit_cost: string };
type ProductionOrderRecord = {
  id: number;
  doc_no: string;
  doc_date: string;
  bom_id: number;
  sales_order_line_id: number | null;
  finished_product_id: number;
  planned_qty: string;
  actual_qty: string | null;
  warehouse_id: number;
  status: 'DRAFT' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED';
  labor_cost: string | null;
  overhead_cost: string | null;
  material_cost: string | null;
  total_cost: string | null;
  unit_cost: string | null;
  consumption: ConsumptionLine[];
  outputs: OutputLine[];
};

function todayLocalDate(): string {
  const today = new Date();
  const month = String(today.getMonth() + 1).padStart(2, '0');
  const day = String(today.getDate()).padStart(2, '0');
  return `${today.getFullYear()}-${month}-${day}`;
}

function ProductionOrdersContent() {
  const permissions = useSessionProfile()?.permissions ?? [];
  const canRead = permissions.includes('production.orders.read');
  const canCreate = permissions.includes('production.orders.create');
  const canUpdate = permissions.includes('production.orders.update');
  const [options, setOptions] = useState<ProductionOptions>({
    boms: [],
    warehouses: [],
    sales_order_lines: [],
  });
  const [orders, setOrders] = useState<ProductionOrderRecord[]>([]);
  const [selected, setSelected] = useState<ProductionOrderRecord | null>(null);
  const [detailId, setDetailId] = useState<number | null>(null);
  const [docDate, setDocDate] = useState(todayLocalDate);
  const [bomId, setBomId] = useState('');
  const [salesOrderLineId, setSalesOrderLineId] = useState('');
  const [plannedQty, setPlannedQty] = useState('');
  const [warehouseId, setWarehouseId] = useState('');
  const [completionId, setCompletionId] = useState<number | null>(null);
  const [actualQty, setActualQty] = useState('');
  const [laborCost, setLaborCost] = useState('0.00');
  const [overheadCost, setOverheadCost] = useState('0.00');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    const [loadedOptions, loadedOrders] = await Promise.all([
      apiRequest<ProductionOptions>('/api/v1/production/orders/options'),
      apiRequest<ProductionOrderRecord[]>('/api/v1/production/orders'),
    ]);
    setOptions(loadedOptions);
    setOrders(loadedOrders);
  }, []);

  useEffect(() => {
    if (!canRead) return;
    reload().catch((cause: unknown) =>
      showErrorToast(cause instanceof Error ? cause.message : 'Could not load production orders'),
    );
  }, [canRead, reload]);

  function resetForm() {
    setSelected(null);
    setDocDate(todayLocalDate());
    setBomId('');
    setSalesOrderLineId('');
    setPlannedQty('');
    setWarehouseId('');
    setError('');
  }

  function editOrder(order: ProductionOrderRecord) {
    setSelected(order);
    setDetailId(null);
    setDocDate(order.doc_date);
    setBomId(String(order.bom_id));
    setSalesOrderLineId(
      order.sales_order_line_id === null ? '' : String(order.sales_order_line_id),
    );
    setPlannedQty(order.planned_qty);
    setWarehouseId(String(order.warehouse_id));
    setError('');
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = productionOrderSchema.safeParse({
      doc_date: docDate,
      bom_id: Number(bomId),
      sales_order_line_id: salesOrderLineId ? Number(salesOrderLineId) : null,
      planned_qty: plannedQty,
      warehouse_id: Number(warehouseId),
    });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? 'Check the production order details.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      await apiRequest<ProductionOrderRecord>(
        selected
          ? `/api/v1/production/orders/${selected.id}`
          : '/api/v1/production/orders',
        { method: selected ? 'PUT' : 'POST', body: JSON.stringify(parsed.data) },
      );
      showSuccessToast(selected ? 'Production order updated.' : 'Production order created.');
      resetForm();
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not save production order';
      setError(message);
      showErrorToast(message);
      return;
    } finally {
      setBusy(false);
    }
    try {
      await reload();
    } catch (cause) {
      showErrorToast(
        cause instanceof Error
          ? `Production order saved, but refresh failed: ${cause.message}`
          : 'Production order saved, but refresh failed.',
      );
    }
  }

  async function runAction(
    order: ProductionOrderRecord,
    action: 'start' | 'cancel' | 'complete',
    body?: string,
  ) {
    setBusy(true);
    try {
      await apiRequest<ProductionOrderRecord>(
        `/api/v1/production/orders/${order.id}/${action}`,
        {
          method: 'POST',
          ...(body ? { body } : {}),
        },
      );
      showSuccessToast(
        action === 'start'
          ? 'Production started.'
          : action === 'cancel'
            ? 'Production order cancelled.'
            : 'Production completed.',
      );
      setCompletionId(null);
      setError('');
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not update production order';
      setError(message);
      showErrorToast(message);
      return;
    } finally {
      setBusy(false);
    }
    try {
      await reload();
    } catch (cause) {
      showErrorToast(
        cause instanceof Error
          ? `Production order updated, but refresh failed: ${cause.message}`
          : 'Production order updated, but refresh failed.',
      );
    }
  }

  function openCompletion(order: ProductionOrderRecord) {
    const bom = options.boms.find((item) => item.id === order.bom_id);
    setCompletionId(order.id);
    setActualQty(order.planned_qty);
    setLaborCost(bom?.labor_cost_default ?? '0.00');
    setOverheadCost(bom?.overhead_cost_default ?? '0.00');
    setError('');
  }

  async function completeOrder(event: FormEvent<HTMLFormElement>, order: ProductionOrderRecord) {
    event.preventDefault();
    const parsed = productionOrderCompleteSchema.safeParse({
      actual_qty: actualQty,
      labor_cost: laborCost,
      overhead_cost: overheadCost,
    });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? 'Check the completion details.');
      return;
    }
    await runAction(order, 'complete', JSON.stringify(parsed.data));
  }

  if (!canRead) {
    return (
      <section className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
        Your account does not have permission to view production orders.
      </section>
    );
  }

  const selectedBOM = options.boms.find((bom) => String(bom.id) === bomId);
  const salesOrderLineOptions = options.sales_order_lines.filter(
    (line) => !selectedBOM || line.product_id === selectedBOM.finished_product_id,
  );

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Production Orders</h1>
        <p className="mt-1 text-sm text-slate-600">
          Start production after material checks, then post actual output and costs.
        </p>
      </header>

      {(selected ? canUpdate : canCreate) && (
        <form onSubmit={(event) => void submit(event)} className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-lg font-semibold">{selected ? 'Edit Production Order' : 'New Production Order'}</h2>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <label className="text-sm font-medium text-slate-700">
              Document date<RequiredMark />
              <input
                type="date"
                required
                value={docDate}
                onChange={(event) => setDocDate(event.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              BOM<RequiredMark />
              <SearchableSelect
                aria-label="BOM"
                required
                placeholder="Search or select a BOM"
                value={bomId}
                onChange={(value) => {
                  const nextBOM = options.boms.find((bom) => String(bom.id) === value);
                  if (
                    salesOrderLineId &&
                    options.sales_order_lines.find((line) => String(line.id) === salesOrderLineId)
                      ?.product_id !== nextBOM?.finished_product_id
                  ) {
                    setSalesOrderLineId('');
                  }
                  setBomId(value);
                }}
                options={options.boms.map((bom) => ({
                  value: String(bom.id),
                  label: bom.code,
                }))}
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Sales Order line (optional)
              <SearchableSelect
                aria-label="Sales Order line"
                placeholder="Optional—search Sales Order lines"
                value={salesOrderLineId}
                onChange={(value) => {
                  setSalesOrderLineId(value);
                  const line = salesOrderLineOptions.find((item) => String(item.id) === value);
                  if (line) setWarehouseId(String(line.warehouse_id));
                }}
                options={salesOrderLineOptions.map((line) => ({
                  value: String(line.id),
                  label: `${line.doc_no} · ${line.product_sku} - ${line.product_name} · ordered ${line.qty_ordered}, produced ${line.qty_produced}`,
                }))}
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Planned quantity<RequiredMark />
              <input type="number" step="any"
                required
                inputMode="decimal"
                value={plannedQty}
                onChange={(event) => setPlannedQty(event.target.value)}
                placeholder="e.g. 10.000"
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Warehouse<RequiredMark />
              <SearchableSelect
                aria-label="Warehouse"
                required
                placeholder="Search or select a warehouse"
                value={warehouseId}
                onChange={setWarehouseId}
                options={options.warehouses.map((warehouse) => ({
                  value: String(warehouse.id),
                  label: `${warehouse.code} - ${warehouse.name}`,
                }))}
              />
            </label>
          </div>
          {error && <FieldError id="production-order-error" message={error} />}
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={busy}
              className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {busy ? 'Saving…' : selected ? 'Save Production Order' : 'Create Production Order'}
            </button>
            {selected && (
              <button type="button" onClick={resetForm} className="rounded-md border border-slate-300 px-4 py-2 text-sm">
                Cancel edit
              </button>
            )}
          </div>
        </form>
      )}

      {error && !selected && <FieldError id="production-action-error" message={error} />}

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-600">
            <tr>
              <th className="px-4 py-3">Document</th>
              <th className="px-4 py-3">BOM</th>
              <th className="px-4 py-3">Planned / actual</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Cost / unit</th>
              {(canUpdate || canRead) && <th className="px-4 py-3">Actions / details</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {orders.map((order) => (
              <tr key={order.id} className="align-top">
                <td className="px-4 py-3">
                  <div className="font-medium">{order.doc_no}</div>
                  <div className="text-xs text-slate-500">{order.doc_date}</div>
                </td>
                <td className="px-4 py-3">
                  {options.boms.find((bom) => bom.id === order.bom_id)?.code ?? `BOM ${order.bom_id}`}
                </td>
                <td className="px-4 py-3">{order.planned_qty} / {order.actual_qty ?? '—'}</td>
                <td className="px-4 py-3">{statusLabel(order.status)}</td>
                <td className="px-4 py-3">
                  {order.unit_cost === null ? '—' : `${order.unit_cost} / unit`}
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {canUpdate && order.status === 'DRAFT' && (
                      <>
                        <IconActionButton
                          icon="edit"
                          label="Edit"
                          tooltip={`Edit production order ${order.doc_no}`}
                          disabled={busy}
                          onClick={() => editOrder(order)}
                          className="p-2 text-emerald-800 hover:bg-emerald-50"
                        />
                        <IconActionButton
                          icon="start"
                          label="Start"
                          tooltip={`Start production order ${order.doc_no}`}
                          disabled={busy}
                          onClick={() => void runAction(order, 'start')}
                          className="p-2 text-emerald-800 hover:bg-emerald-50"
                        />
                      </>
                    )}
                    {canUpdate && order.status === 'IN_PROGRESS' && (
                      <IconActionButton
                        icon="complete"
                        label="Complete"
                        tooltip={`Complete production order ${order.doc_no}`}
                        disabled={busy}
                        onClick={() => openCompletion(order)}
                        className="p-2 text-emerald-800 hover:bg-emerald-50"
                      />
                    )}
                    {canUpdate && ['DRAFT', 'IN_PROGRESS'].includes(order.status) && (
                      <IconActionButton
                        icon="cancel"
                        label="Cancel"
                        tooltip={`Cancel production order ${order.doc_no}`}
                        disabled={busy}
                        onClick={() => void runAction(order, 'cancel')}
                        className="p-2 text-rose-700 hover:bg-rose-50"
                      />
                    )}
                    <IconActionButton
                      icon="view"
                      label={detailId === order.id ? 'Hide details' : 'Details'}
                      tooltip={`${detailId === order.id ? 'Hide' : 'View'} details for ${order.doc_no}`}
                      aria-expanded={detailId === order.id}
                      onClick={() => setDetailId(detailId === order.id ? null : order.id)}
                      className="p-2 text-slate-700 hover:bg-slate-100"
                    />
                  </div>
                  {completionId === order.id && (
                    <form onSubmit={(event) => void completeOrder(event, order)} className="mt-3 grid min-w-64 gap-2 rounded-lg bg-slate-50 p-3">
                      <label className="text-xs text-slate-700">
                        Actual output quantity<RequiredMark />
                        <input type="number" step="any"
                          required
                          inputMode="decimal"
                          value={actualQty}
                          onChange={(event) => setActualQty(event.target.value)}
                          placeholder="e.g. 10.000"
                          className="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1"
                        />
                      </label>
                      <label className="text-xs text-slate-700">
                        Labor cost<RequiredMark />
                        <input type="number" step="any"
                          required
                          inputMode="decimal"
                          value={laborCost}
                          onChange={(event) => setLaborCost(event.target.value)}
                          placeholder="e.g. 25.00"
                          className="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1"
                        />
                      </label>
                      <label className="text-xs text-slate-700">
                        Overhead cost<RequiredMark />
                        <input type="number" step="any"
                          required
                          inputMode="decimal"
                          value={overheadCost}
                          onChange={(event) => setOverheadCost(event.target.value)}
                          placeholder="e.g. 10.00"
                          className="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1"
                        />
                      </label>
                      <button type="submit" disabled={busy} className="rounded bg-emerald-700 px-3 py-2 text-xs font-medium text-white">
                        Post production
                      </button>
                    </form>
                  )}
                  {detailId === order.id && (
                    <div className="mt-3 min-w-64 space-y-2 text-xs text-slate-700">
                      <p>Materials: {order.material_cost ?? '—'} · Labor: {order.labor_cost ?? '—'} · Overhead: {order.overhead_cost ?? '—'} · Total: {order.total_cost ?? '—'}</p>
                      <p>Consumption: {order.consumption.map((line) => `${line.product_id}: ${line.qty} × ${line.unit_cost} = ${line.line_cost}`).join('; ') || 'None'}</p>
                      <p>Output: {order.outputs.map((line) => `${line.product_id}: ${line.qty} at ${line.unit_cost}/unit`).join('; ') || 'None'}</p>
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {orders.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-5 text-slate-600">No production orders found.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function ProductionOrdersPage() {
  return (
    <ProtectedPage>
      <ProductionOrdersContent />
    </ProtectedPage>
  );
}
