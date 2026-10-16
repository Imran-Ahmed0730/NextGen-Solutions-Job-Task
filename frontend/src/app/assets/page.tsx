'use client';

import { useCallback, useEffect, useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { useSessionProfile } from '@/components/auth/session-shell';
import { FieldError, getFieldErrors, RequiredMark, type FieldErrors } from '@/components/forms/field-error';
import { IconActionButton } from '@/components/ui/action-icon';
import { apiRequest } from '@/lib/auth-api';
import { statusLabel } from '@/lib/display-labels';
import {
  assetAssignmentSchema,
  assetMaintenanceSchema,
  assetSchema,
} from '@/lib/auth-validation';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';

type Assignment = {
  id: number;
  location: string;
  assigned_on: string;
  returned_on: string | null;
};

type Maintenance = {
  id: number;
  maintenance_date: string;
  description: string;
  cost: string;
  next_due_date: string | null;
};

type AssetRecord = {
  id: number;
  asset_code: string;
  name: string;
  category: string;
  purchase_date: string;
  purchase_cost: string;
  location: string;
  status: string;
  is_active: boolean;
  assignments: Assignment[];
  maintenance: Maintenance[];
};

type AssetAction = { type: 'assign' | 'maintenance'; asset: AssetRecord } | null;

function AssetsContent() {
  const profile = useSessionProfile();
  const [assets, setAssets] = useState<AssetRecord[]>([]);
  const [selected, setSelected] = useState<AssetRecord | null>(null);
  const [action, setAction] = useState<AssetAction>(null);
  const [includeInactive, setIncludeInactive] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});

  const reload = useCallback(async () => {
    const query = includeInactive ? '?include_inactive=true' : '';
    setAssets(await apiRequest<AssetRecord[]>(`/api/v1/assets${query}`));
  }, [includeInactive]);

  useEffect(() => {
    void reload().catch((cause: unknown) =>
      showErrorToast(cause instanceof Error ? cause.message : 'Could not load assets'),
    );
  }, [reload]);

  async function submitAsset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const parsed = assetSchema.safeParse({
      asset_code: form.get('asset_code'),
      name: form.get('name'),
      category: form.get('category'),
      purchase_date: form.get('purchase_date'),
      purchase_cost: form.get('purchase_cost'),
      location: form.get('location'),
      status: form.get('status') ?? 'IN_STORE',
    });
    if (!parsed.success) {
      setErrors(getFieldErrors(parsed.error.issues));
      return;
    }
    setErrors({});
    try {
      await apiRequest<AssetRecord>(
        selected ? `/api/v1/assets/${selected.id}` : '/api/v1/assets',
        {
          method: selected ? 'PATCH' : 'POST',
          body: JSON.stringify(parsed.data),
        },
      );
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not save asset');
      return;
    }
    showSuccessToast(selected ? 'Asset updated.' : 'Asset created.');
    setSelected(null);
    try {
      await reload();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not refresh the asset list');
    }
  }

  async function submitAction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!action) return;
    const form = new FormData(event.currentTarget);
    const parsed =
      action.type === 'assign'
        ? assetAssignmentSchema.safeParse({
            location: form.get('location'),
            assigned_on: form.get('assigned_on'),
          })
        : assetMaintenanceSchema.safeParse({
            maintenance_date: form.get('maintenance_date'),
            description: form.get('description'),
            cost: form.get('cost'),
            next_due_date: form.get('next_due_date') || undefined,
          });
    if (!parsed.success) {
      setErrors(getFieldErrors(parsed.error.issues));
      return;
    }
    setErrors({});
    try {
      await apiRequest<AssetRecord>(`/api/v1/assets/${action.asset.id}/${action.type === 'assign' ? 'assignments' : 'maintenance'}`, {
        method: 'POST',
        body: JSON.stringify(parsed.data),
      });
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not save asset details');
      return;
    }
    showSuccessToast(action.type === 'assign' ? 'Asset assigned.' : 'Maintenance recorded.');
    setAction(null);
    try {
      await reload();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not refresh the asset list');
    }
  }

  async function updateAssetStatus(asset: AssetRecord, operation: 'delete' | 'restore') {
    try {
      await apiRequest<AssetRecord>(
        operation === 'delete' ? `/api/v1/assets/${asset.id}` : `/api/v1/assets/${asset.id}/restore`,
        { method: operation === 'delete' ? 'DELETE' : 'POST' },
      );
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not update asset');
      return;
    }
    showSuccessToast(operation === 'delete' ? 'Asset deleted.' : 'Asset restored.');
    try {
      await reload();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not refresh the asset list');
    }
  }

  async function returnAssignment(asset: AssetRecord, assignment: Assignment) {
    const returnedOn = new Date().toISOString().slice(0, 10);
    try {
      await apiRequest<AssetRecord>(
        `/api/v1/assets/${asset.id}/assignments/${assignment.id}/return?returned_on=${returnedOn}`,
        { method: 'POST' },
      );
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not return asset');
      return;
    }
    showSuccessToast('Asset returned to store.');
    try {
      await reload();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not refresh the asset list');
    }
  }

  return (
    <main className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Assets</h1>
        <p className="mt-1 text-sm text-slate-600">
          Register assets, track location assignments, and record maintenance.
        </p>
      </div>

      {profile?.permissions.includes(selected ? 'assets.update' : 'assets.create') && (
        <form
          key={selected?.id ?? 'new-asset'}
          noValidate
          onSubmit={submitAsset}
          className="grid gap-4 rounded-lg border border-slate-200 p-4 sm:grid-cols-2 lg:grid-cols-3"
        >
          <label className="text-sm font-medium">
            Asset code<RequiredMark />
            <input type="text"
              name="asset_code"
              placeholder="e.g. AST-001"
              defaultValue={selected?.asset_code ?? ''}
              required
              aria-invalid={Boolean(errors.asset_code)}
              aria-describedby={errors.asset_code ? 'asset-code-error' : undefined}
              className="mt-1 w-full rounded-md border px-3 py-2"
            />
            <FieldError id="asset-code-error" message={errors.asset_code} />
          </label>
          <label className="text-sm font-medium">
            Asset name<RequiredMark />
            <input type="text"
              name="name"
              placeholder="e.g. Office printer"
              defaultValue={selected?.name ?? ''}
              required
              aria-invalid={Boolean(errors.name)}
              aria-describedby={errors.name ? 'asset-name-error' : undefined}
              className="mt-1 w-full rounded-md border px-3 py-2"
            />
            <FieldError id="asset-name-error" message={errors.name} />
          </label>
          <label className="text-sm font-medium">
            Category<RequiredMark />
            <input type="text"
              name="category"
              placeholder="e.g. Office equipment"
              defaultValue={selected?.category ?? ''}
              required
              aria-invalid={Boolean(errors.category)}
              aria-describedby={errors.category ? 'asset-category-error' : undefined}
              className="mt-1 w-full rounded-md border px-3 py-2"
            />
            <FieldError id="asset-category-error" message={errors.category} />
          </label>
          <label className="text-sm font-medium">
            Purchase date<RequiredMark />
            <input
              name="purchase_date"
              type="date"
              defaultValue={selected?.purchase_date ?? ''}
              required
              aria-invalid={Boolean(errors.purchase_date)}
              aria-describedby={
                errors.purchase_date ? 'asset-purchase-date-error' : undefined
              }
              className="mt-1 w-full rounded-md border px-3 py-2"
            />
            <FieldError id="asset-purchase-date-error" message={errors.purchase_date} />
          </label>
          <label className="text-sm font-medium">
            Purchase cost<RequiredMark />
            <input
              name="purchase_cost"
              type="number"
              min="0"
              step="0.01"
              placeholder="e.g. 25000.00"
              defaultValue={selected?.purchase_cost ?? ''}
              required
              aria-invalid={Boolean(errors.purchase_cost)}
              aria-describedby={
                errors.purchase_cost ? 'asset-purchase-cost-error' : undefined
              }
              className="mt-1 w-full rounded-md border px-3 py-2"
            />
            <FieldError id="asset-purchase-cost-error" message={errors.purchase_cost} />
          </label>
          <label className="text-sm font-medium">
            Current location<RequiredMark />
            <input type="text"
              name="location"
              placeholder="e.g. Main office"
              defaultValue={selected?.location ?? ''}
              required
              aria-invalid={Boolean(errors.location)}
              aria-describedby={errors.location ? 'asset-location-error' : undefined}
              className="mt-1 w-full rounded-md border px-3 py-2"
            />
            <FieldError id="asset-location-error" message={errors.location} />
          </label>
          {selected && (
            <label className="text-sm font-medium">
              Status<RequiredMark />
              <select
                name="status"
                defaultValue={selected.status}
                required
                className="mt-1 w-full rounded-md border px-3 py-2"
              >
                <option value="IN_STORE">In store</option>
                <option value="IN_USE">In use</option>
                <option value="UNDER_MAINTENANCE">Under maintenance</option>
                <option value="DISPOSED">Disposed</option>
              </select>
            </label>
          )}
          <div className="flex gap-2 sm:col-span-2 lg:col-span-3">
            <button className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white">
              {selected ? 'Save asset' : 'Add asset'}
            </button>
            {selected && (
              <button
                type="button"
                onClick={() => setSelected(null)}
                className="rounded-md border px-4 py-2 text-sm"
              >
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
        Show deleted assets
      </label>

      <div className="space-y-4">
        {assets.map((asset) => {
          return (
            <article
              key={asset.id}
              className="rounded-lg border border-slate-200 p-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="font-semibold">
                    {asset.name}{' '}
                    <span className="font-normal text-slate-500">
                      ({asset.asset_code})
                    </span>
                  </h2>
                  <p className="mt-1 text-sm text-slate-600">
                    {asset.category} · {asset.location} ·{' '}
                    {statusLabel(asset.status)} ·{' '}
                    {asset.is_active ? 'Active' : 'Deleted'}
                  </p>
                  <p className="mt-1 text-sm text-slate-600">
                    Purchased {asset.purchase_date} for {asset.purchase_cost}
                  </p>
                </div>
                <div className="flex flex-wrap gap-1">
                  {asset.is_active && profile?.permissions.includes('assets.update') && (
                    <IconActionButton
                      icon="edit"
                      label={`Edit ${asset.name}`}
                      onClick={() => {
                        setSelected(asset);
                        setAction(null);
                      }}
                      className="p-2 text-emerald-800 hover:bg-emerald-50"
                    />
                  )}
                  {asset.is_active && profile?.permissions.includes('assets.delete') && (
                    <IconActionButton
                      icon="delete"
                      label={`Delete ${asset.name}`}
                      onClick={() => void updateAssetStatus(asset, 'delete')}
                      className="p-2 text-rose-700 hover:bg-rose-50"
                    />
                  )}
                  {!asset.is_active && profile?.permissions.includes('assets.update') && (
                    <IconActionButton
                      icon="restore"
                      label={`Restore ${asset.name}`}
                      onClick={() => void updateAssetStatus(asset, 'restore')}
                      className="p-2 text-emerald-800 hover:bg-emerald-50"
                    />
                  )}
                  {asset.is_active && profile?.permissions.includes('assets.assign') && (
                    <IconActionButton
                      icon="assign"
                      label={`Assign location for ${asset.name}`}
                      onClick={() => {
                        setSelected(null);
                        setErrors({});
                        setAction({ type: 'assign', asset });
                      }}
                      className="p-2 text-slate-700 hover:bg-slate-100"
                    />
                  )}
                  {asset.is_active && profile?.permissions.includes('assets.maintain') && (
                    <IconActionButton
                      icon="maintenance"
                      label={`Record maintenance for ${asset.name}`}
                      onClick={() => {
                        setSelected(null);
                        setErrors({});
                        setAction({ type: 'maintenance', asset });
                      }}
                      className="p-2 text-slate-700 hover:bg-slate-100"
                    />
                  )}
                </div>
              </div>

              {action?.asset.id === asset.id && (
                <form
                  noValidate
                  onSubmit={submitAction}
                  className="mt-4 grid gap-3 rounded-md bg-slate-50 p-3 sm:grid-cols-2"
                >
                  {action.type === 'assign' ? (
                    <>
                      <label className="text-sm font-medium">
                        Assigned location<RequiredMark />
                        <input type="text"
                          name="location"
                          placeholder="e.g. Accounts office"
                          required
                          aria-invalid={Boolean(errors.location)}
                          aria-describedby={
                            errors.location ? 'assignment-location-error' : undefined
                          }
                          className="mt-1 w-full rounded border px-3 py-2"
                        />
                        <FieldError id="assignment-location-error" message={errors.location} />
                      </label>
                      <label className="text-sm font-medium">
                        Assigned date<RequiredMark />
                        <input
                          name="assigned_on"
                          type="date"
                          required
                          aria-invalid={Boolean(errors.assigned_on)}
                          aria-describedby={
                            errors.assigned_on ? 'assignment-date-error' : undefined
                          }
                          className="mt-1 w-full rounded border px-3 py-2"
                        />
                        <FieldError id="assignment-date-error" message={errors.assigned_on} />
                      </label>
                    </>
                  ) : (
                    <>
                      <label className="text-sm font-medium">
                        Maintenance date<RequiredMark />
                        <input
                          name="maintenance_date"
                          type="date"
                          required
                          aria-invalid={Boolean(errors.maintenance_date)}
                          aria-describedby={
                            errors.maintenance_date
                              ? 'maintenance-date-error'
                              : undefined
                          }
                          className="mt-1 w-full rounded border px-3 py-2"
                        />
                        <FieldError id="maintenance-date-error" message={errors.maintenance_date} />
                      </label>
                      <label className="text-sm font-medium">
                        Cost<RequiredMark />
                        <input
                          name="cost"
                          type="number"
                          min="0"
                          step="0.01"
                          placeholder="e.g. 500.00"
                          required
                          aria-invalid={Boolean(errors.cost)}
                          aria-describedby={
                            errors.cost ? 'maintenance-cost-error' : undefined
                          }
                          className="mt-1 w-full rounded border px-3 py-2"
                        />
                        <FieldError id="maintenance-cost-error" message={errors.cost} />
                      </label>
                      <label className="text-sm font-medium sm:col-span-2">
                        Description<RequiredMark />
                        <textarea
                          name="description"
                          placeholder="Describe the maintenance performed"
                          required
                          aria-invalid={Boolean(errors.description)}
                          aria-describedby={
                            errors.description
                              ? 'maintenance-description-error'
                              : undefined
                          }
                          className="mt-1 w-full rounded border px-3 py-2"
                        />
                        <FieldError id="maintenance-description-error" message={errors.description} />
                      </label>
                      <label className="text-sm font-medium">
                        Next due date
                        <input
                          name="next_due_date"
                          type="date"
                          className="mt-1 w-full rounded border px-3 py-2"
                        />
                      </label>
                    </>
                  )}
                  <div className="flex gap-2 sm:col-span-2">
                    <button className="rounded bg-emerald-700 px-3 py-2 text-sm text-white">Save</button>
                    <button
                      type="button"
                      onClick={() => setAction(null)}
                      className="rounded border px-3 py-2 text-sm"
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              )}

              <div className="mt-4 grid gap-4 text-sm md:grid-cols-2">
                <section>
                  <h3 className="font-medium">Location history</h3>
                  {asset.assignments.length ? (
                    <ul className="mt-1 space-y-1 text-slate-600">
                      {asset.assignments.map((assignment) => (
                        <li
                          key={assignment.id}
                          className="flex flex-wrap items-center gap-2"
                        >
                          {assignment.location}: {assignment.assigned_on} –{' '}
                          {assignment.returned_on ?? 'Current'}
                          {!assignment.returned_on && profile?.permissions.includes('assets.assign') && (
                            <IconActionButton
                              icon="return"
                              label={`Return ${asset.name} to store`}
                              onClick={() => void returnAssignment(asset, assignment)}
                              className="p-1 text-emerald-800 hover:bg-emerald-50"
                            />
                          )}
                        </li>
                      ))}
                    </ul>
                  ) : <p className="mt-1 text-slate-500">No location assignments recorded.</p>}
                </section>
                <section>
                  <h3 className="font-medium">Maintenance history</h3>
                  {asset.maintenance.length ? (
                    <ul className="mt-1 space-y-1 text-slate-600">
                      {asset.maintenance.map((record) => (
                        <li key={record.id}>
                          {record.maintenance_date}: {record.description} ({record.cost})
                          {record.next_due_date ? ` · Next due ${record.next_due_date}` : ''}
                        </li>
                      ))}
                    </ul>
                  ) : <p className="mt-1 text-slate-500">No maintenance recorded.</p>}
                </section>
              </div>
            </article>
          );
        })}
        {assets.length === 0 && (
          <p className="rounded-lg border p-8 text-center text-sm text-slate-500">
            No assets found.
          </p>
        )}
      </div>
    </main>
  );
}

export default function AssetsPage() {
  return (
    <ProtectedPage>
      <AssetsContent />
    </ProtectedPage>
  );
}
