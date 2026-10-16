'use client';

import { useCallback, useEffect, useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { useSessionProfile } from '@/components/auth/session-shell';
import { FieldError, RequiredMark } from '@/components/forms/field-error';
import { SearchableSelect } from '@/components/forms/searchable-select';
import { IconActionButton } from '@/components/ui/action-icon';
import { apiRequest } from '@/lib/auth-api';
import { bomSchema } from '@/lib/auth-validation';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';

type ProductOption = {
  id: number;
  sku: string;
  name: string;
  unit_code: string;
  type: 'RAW' | 'FINISHED';
};
type BOMOptions = { raw_products: ProductOption[]; finished_products: ProductOption[] };
type BOMLine = { id: number; raw_product_id: number; qty: string };
type BOMRecord = {
  id: number;
  code: string;
  finished_product_id: number;
  output_qty: string;
  labor_cost_default: string;
  overhead_cost_default: string;
  is_active: boolean;
  deleted_at: string | null;
  lines: BOMLine[];
};
type DraftLine = { raw_product_id: string; qty: string };

const blankLine = (): DraftLine => ({ raw_product_id: '', qty: '' });

function BOMsContent() {
  const profile = useSessionProfile();
  const permissions = profile?.permissions ?? [];
  const canRead = permissions.includes('production.boms.read');
  const canCreate = permissions.includes('production.boms.create');
  const canUpdate = permissions.includes('production.boms.update');
  const canDelete = permissions.includes('production.boms.delete');
  const [boms, setBoms] = useState<BOMRecord[]>([]);
  const [options, setOptions] = useState<BOMOptions>({
    raw_products: [],
    finished_products: [],
  });
  const [selected, setSelected] = useState<BOMRecord | null>(null);
  const [includeInactive, setIncludeInactive] = useState(false);
  const [code, setCode] = useState('');
  const [finishedProductId, setFinishedProductId] = useState('');
  const [outputQty, setOutputQty] = useState('');
  const [laborCost, setLaborCost] = useState('0.00');
  const [overheadCost, setOverheadCost] = useState('0.00');
  const [lines, setLines] = useState<DraftLine[]>([blankLine()]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    const query = includeInactive ? '?include_inactive=true' : '';
    const [loadedOptions, loadedBOMs] = await Promise.all([
      apiRequest<BOMOptions>('/api/v1/production/boms/options'),
      apiRequest<BOMRecord[]>(`/api/v1/production/boms${query}`),
    ]);
    setOptions(loadedOptions);
    setBoms(loadedBOMs);
  }, [includeInactive]);

  useEffect(() => {
    if (!canRead) return;
    reload().catch((cause: unknown) =>
      showErrorToast(cause instanceof Error ? cause.message : 'Could not load BOMs'),
    );
  }, [canRead, reload]);

  function resetForm() {
    setSelected(null);
    setCode('');
    setFinishedProductId('');
    setOutputQty('');
    setLaborCost('0.00');
    setOverheadCost('0.00');
    setLines([blankLine()]);
    setError('');
  }

  function editBOM(bom: BOMRecord) {
    setSelected(bom);
    setCode(bom.code);
    setFinishedProductId(String(bom.finished_product_id));
    setOutputQty(bom.output_qty);
    setLaborCost(bom.labor_cost_default);
    setOverheadCost(bom.overhead_cost_default);
    setLines(bom.lines.map((line) => ({
      raw_product_id: String(line.raw_product_id),
      qty: line.qty,
    })));
    setError('');
  }

  function updateLine(index: number, key: keyof DraftLine, value: string) {
    setLines((current) =>
      current.map((line, lineIndex) => lineIndex === index ? { ...line, [key]: value } : line),
    );
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = bomSchema.safeParse({
      code,
      finished_product_id: Number(finishedProductId),
      output_qty: outputQty,
      labor_cost_default: laborCost,
      overhead_cost_default: overheadCost,
      lines: lines.map((line) => ({
        raw_product_id: Number(line.raw_product_id),
        qty: line.qty,
      })),
    });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? 'Check the BOM details.');
      return;
    }
    setError('');
    setBusy(true);
    try {
      await apiRequest<BOMRecord>(
        selected ? `/api/v1/production/boms/${selected.id}` : '/api/v1/production/boms',
        {
          method: selected ? 'PUT' : 'POST',
          body: JSON.stringify(parsed.data),
        },
      );
      showSuccessToast(selected ? 'BOM updated.' : 'BOM created.');
      resetForm();
      try {
        await reload();
      } catch (cause) {
        showErrorToast(
          cause instanceof Error ? `BOM saved, but refresh failed: ${cause.message}` : 'BOM saved, but refresh failed',
        );
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not save BOM');
      showErrorToast(cause instanceof Error ? cause.message : 'Could not save BOM');
    } finally {
      setBusy(false);
    }
  }

  async function setActive(bom: BOMRecord, active: boolean) {
    try {
      await apiRequest<BOMRecord>(
        active
          ? `/api/v1/production/boms/${bom.id}/activate`
          : `/api/v1/production/boms/${bom.id}`,
        { method: active ? 'POST' : 'DELETE' },
      );
      showSuccessToast(active ? 'BOM restored.' : 'BOM deleted.');
      if (selected?.id === bom.id) resetForm();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not update BOM');
      return;
    }
    try {
      await reload();
    } catch (cause) {
      showErrorToast(
        cause instanceof Error
          ? `BOM updated, but the list could not be refreshed: ${cause.message}`
          : 'BOM updated, but the list could not be refreshed.',
      );
    }
  }

  if (!canRead) {
    return (
      <section className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
        Your account does not have permission to view bills of materials.
      </section>
    );
  }

  const finishedLabel = (productId: number) => {
    const product = options.finished_products.find((item) => item.id === productId);
    return product ? `${product.sku} - ${product.name}` : `Product ${productId}`;
  };

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Bills of Materials</h1>
        <p className="mt-1 text-sm text-slate-600">
          Define the raw materials and quantities needed for each finished-goods output.
        </p>
      </header>

      {(selected ? canUpdate : canCreate) && (
        <form onSubmit={(event) => void submit(event)} className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-lg font-semibold">{selected ? 'Edit BOM' : 'New BOM'}</h2>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <label className="text-sm font-medium text-slate-700">
              BOM code<RequiredMark />
              <input type="text"
                required
                value={code}
                onChange={(event) => setCode(event.target.value)}
                placeholder="e.g. BOM-BREAD-01"
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Finished product<RequiredMark />
              <SearchableSelect
                aria-label="Finished product"
                required
                placeholder="Search or select finished product"
                value={finishedProductId}
                onChange={setFinishedProductId}
                options={options.finished_products.map((product) => ({
                  value: String(product.id),
                  label: `${product.sku} - ${product.name}`,
                }))}
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Output quantity<RequiredMark />
              <input type="number" step="any"
                required
                inputMode="decimal"
                value={outputQty}
                onChange={(event) => setOutputQty(event.target.value)}
                placeholder="e.g. 10.000"
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Default labor cost
              <input type="number" step="any"
                inputMode="decimal"
                value={laborCost}
                onChange={(event) => setLaborCost(event.target.value)}
                placeholder="0.00"
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Default overhead cost
              <input type="number" step="any"
                inputMode="decimal"
                value={overheadCost}
                onChange={(event) => setOverheadCost(event.target.value)}
                placeholder="0.00"
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
          </div>

          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-slate-800">Raw material lines</h3>
            {lines.map((line, index) => (
              <div key={index} className="grid gap-3 rounded-lg bg-slate-50 p-3 md:grid-cols-3">
                <label className="text-sm text-slate-700">
                  Raw material<RequiredMark />
                  <SearchableSelect
                    aria-label={`Raw material ${index + 1}`}
                    required
                    placeholder="Search or select raw material"
                    value={line.raw_product_id}
                    onChange={(value) => updateLine(index, 'raw_product_id', value)}
                    options={options.raw_products.map((product) => ({
                      value: String(product.id),
                      label: `${product.sku} - ${product.name}`,
                    }))}
                  />
                </label>
                <label className="text-sm text-slate-700">
                  Quantity<RequiredMark />
                  <input type="number" step="any"
                    required
                    inputMode="decimal"
                    value={line.qty}
                    onChange={(event) => updateLine(index, 'qty', event.target.value)}
                    placeholder="e.g. 2.500"
                    className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2"
                  />
                </label>
                <div className="flex items-end">
                  <button
                    type="button"
                    disabled={lines.length === 1}
                    onClick={() => setLines((current) => current.filter((_, i) => i !== index))}
                    className="rounded-md border border-slate-300 px-3 py-2 text-sm disabled:opacity-50"
                  >
                    Remove line
                  </button>
                </div>
              </div>
            ))}
            <button
              type="button"
              onClick={() => setLines((current) => [...current, blankLine()])}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
            >
              Add raw material
            </button>
          </div>
          {error && <FieldError id="bom-error" message={error} />}
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={busy}
              className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {busy ? 'Saving…' : selected ? 'Save BOM' : 'Create BOM'}
            </button>
            {selected && (
              <button type="button" onClick={resetForm} className="rounded-md border border-slate-300 px-4 py-2 text-sm">
                Cancel
              </button>
            )}
          </div>
        </form>
      )}

      <label className="inline-flex items-center gap-2 text-sm text-slate-600">
        <input
          type="checkbox"
          checked={includeInactive}
          onChange={(event) => setIncludeInactive(event.target.checked)}
        />
        Show deleted BOMs
      </label>

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-600">
            <tr>
              <th className="px-4 py-3">BOM code</th>
              <th className="px-4 py-3">Finished product</th>
              <th className="px-4 py-3">Output quantity</th>
              <th className="px-4 py-3">Materials</th>
              <th className="px-4 py-3">Status</th>
              {(canUpdate || canDelete) && <th className="px-4 py-3">Actions</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {boms.map((bom) => (
              <tr key={bom.id}>
                <td className="px-4 py-3 font-medium">{bom.code}</td>
                <td className="px-4 py-3">{finishedLabel(bom.finished_product_id)}</td>
                <td className="px-4 py-3">{bom.output_qty}</td>
                <td className="px-4 py-3">
                  {bom.lines.map((line) => {
                    const product = options.raw_products.find((item) => item.id === line.raw_product_id);
                    return `${product?.sku ?? line.raw_product_id}: ${line.qty}${product ? ` ${product.unit_code}` : ''}`;
                  }).join(', ')}
                </td>
                <td className="px-4 py-3">{bom.is_active ? 'Active' : 'Deleted'}</td>
                {(canUpdate || canDelete) && (
                  <td className="px-4 py-3">
                    {bom.deleted_at ? (
                      canUpdate && (
                        <IconActionButton
                          icon="restore"
                          label={`Restore BOM ${bom.code}`}
                          onClick={() => void setActive(bom, true)}
                          className="p-2 text-emerald-800 hover:bg-emerald-50"
                        />
                      )
                    ) : (
                      <div className="flex gap-1">
                        {canUpdate && (
                          <IconActionButton
                            icon="edit"
                            label={`Edit BOM ${bom.code}`}
                            onClick={() => editBOM(bom)}
                            className="p-2 text-emerald-800 hover:bg-emerald-50"
                          />
                        )}
                        {canDelete && (
                          <IconActionButton
                            icon="delete"
                            label={`Delete BOM ${bom.code}`}
                            onClick={() => void setActive(bom, false)}
                            className="p-2 text-rose-700 hover:bg-rose-50"
                          />
                        )}
                      </div>
                    )}
                  </td>
                )}
              </tr>
            ))}
            {boms.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-5 text-slate-600">No BOMs found.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function BOMsPage() {
  return (
    <ProtectedPage>
      <BOMsContent />
    </ProtectedPage>
  );
}
