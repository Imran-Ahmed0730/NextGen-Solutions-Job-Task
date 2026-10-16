'use client';

import { useEffect, useState, type FormEvent } from 'react';
import Swal from 'sweetalert2';

import { ProtectedPage } from '@/components/auth/protected-page';
import { useSessionProfile } from '@/components/auth/session-shell';
import {
  FieldError,
  getApiFieldErrors,
  getFieldErrors,
  RequiredMark,
  type FieldErrors,
} from '@/components/forms/field-error';
import { StatusSwitch } from '@/components/forms/status-switch';
import { ActionIcon, IconActionButton } from '@/components/ui/action-icon';
import { apiRequest } from '@/lib/auth-api';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';
import { warehouseSchema } from '@/lib/auth-validation';

type WarehouseRecord = {
  id: number;
  name: string;
  code: string;
  address: string | null;
  is_default: boolean;
  is_active: boolean;
  deleted_at: string | null;
};

function WarehousesContent() {
  const profile = useSessionProfile();
  const [warehouses, setWarehouses] = useState<WarehouseRecord[]>([]);
  const [selected, setSelected] = useState<WarehouseRecord | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [includeInactive, setIncludeInactive] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});

  async function reload() {
    const query = includeInactive ? '?include_inactive=true' : '';
    setWarehouses(await apiRequest<WarehouseRecord[]>(`/api/v1/warehouses${query}`));
  }

  useEffect(() => {
    reload().catch((cause: unknown) =>
      showErrorToast(cause instanceof Error ? cause.message : 'Could not load warehouses'),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [includeInactive]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const parsed = warehouseSchema.safeParse({
      name: form.get('name'),
      code: form.get('code'),
      address: form.get('address') || null,
      is_default: form.get('is_default') === 'on',
      is_active: form.get('is_active') === 'on',
    });
    if (!parsed.success) {
      setErrors(getFieldErrors(parsed.error.issues));
      return;
    }
    setErrors({});

    try {
      await apiRequest<WarehouseRecord>(
        selected ? `/api/v1/warehouses/${selected.id}` : '/api/v1/warehouses',
        {
          method: selected ? 'PATCH' : 'POST',
          body: JSON.stringify(parsed.data),
        },
      );
      showSuccessToast(selected ? 'Warehouse updated.' : 'Warehouse created.');
      setSelected(null);
      setIsFormOpen(false);
    } catch (cause) {
      const apiErrors = getApiFieldErrors(cause);
      if (Object.keys(apiErrors).length) setErrors(apiErrors);
      else showErrorToast(cause instanceof Error ? cause.message : 'Could not save warehouse');
      return;
    }
    try {
      await reload();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not refresh warehouse list');
    }
  }

  async function setDeleted(warehouse: WarehouseRecord, deleteAction: boolean) {
    if (deleteAction) {
      const confirmation = await Swal.fire({
        title: 'Delete warehouse?',
        text: `Are you sure you want to delete "${warehouse.name}"? It will be archived and hidden from active lists.`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#b91c1c',
        cancelButtonColor: '#64748b',
        confirmButtonText: 'Yes, delete',
      });
      if (!confirmation.isConfirmed) return;
    }
    try {
      await apiRequest<WarehouseRecord>(
        deleteAction
          ? `/api/v1/warehouses/${warehouse.id}`
          : `/api/v1/warehouses/${warehouse.id}/activate`,
        { method: deleteAction ? 'DELETE' : 'POST' },
      );
      showSuccessToast(deleteAction ? 'Warehouse deleted.' : 'Warehouse restored.');
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not update warehouse status');
      return;
    }
    try {
      await reload();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not refresh warehouse list');
    }
  }

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Warehouses</h1>
          <p className="mt-1 text-sm text-slate-600">
            Manage storage locations used for inventory, purchases, and deliveries.
          </p>
        </div>
        {profile?.permissions.includes('master_data.warehouses.create') && !isFormOpen && (
          <button
            type="button"
            onClick={() => {
              setErrors({});
              setSelected(null);
              setIsFormOpen(true);
            }}
            className="inline-flex items-center gap-2 rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-emerald-800"
          >
            <ActionIcon name="add" />
            Add warehouse
          </button>
        )}
      </div>

      {isFormOpen && (
        <form
          key={selected?.id ?? 'new-warehouse'}
          noValidate
          className="mt-6 grid max-w-4xl gap-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm sm:grid-cols-2"
          onSubmit={submit}
        >
          <div className="sm:col-span-2">
            <h2 className="text-lg font-medium text-slate-900">
              {selected ? 'Edit warehouse' : 'New warehouse'}
            </h2>
          </div>

          <label className="block text-sm font-medium">
            Warehouse name<RequiredMark />
            <input type="text"
              name="name"
              placeholder="e.g. Main Store"
              defaultValue={selected?.name ?? ''}
              minLength={1}
              maxLength={100}
              required
              aria-invalid={Boolean(errors.name)}
              aria-describedby={errors.name ? 'warehouse-name-error' : undefined}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            />
            <FieldError id="warehouse-name-error" message={errors.name} />
          </label>

          <label className="block text-sm font-medium">
            Warehouse code<RequiredMark />
            <input type="text"
              name="code"
              placeholder="e.g. MS"
              defaultValue={selected?.code ?? ''}
              minLength={1}
              maxLength={30}
              required
              aria-invalid={Boolean(errors.code)}
              aria-describedby={errors.code ? 'warehouse-code-error' : undefined}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 uppercase"
            />
            <FieldError id="warehouse-code-error" message={errors.code} />
          </label>

          <label className="block text-sm font-medium sm:col-span-2">
            Address
            <input type="text"
              name="address"
              placeholder="Optional street, area, and city"
              defaultValue={selected?.address ?? ''}
              maxLength={255}
              aria-invalid={Boolean(errors.address)}
              aria-describedby={errors.address ? 'warehouse-address-error' : undefined}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            />
            <FieldError id="warehouse-address-error" message={errors.address} />
          </label>

          <div className="flex flex-col justify-center space-y-3">
            <label className="inline-flex cursor-pointer items-center gap-2 text-sm font-medium text-slate-700">
              <input
                type="checkbox"
                name="is_default"
                defaultChecked={selected?.is_default ?? false}
                className="h-4 w-4 rounded border-slate-300 accent-emerald-700"
              />
              Default warehouse
            </label>
            <StatusSwitch
              name="is_active"
              label="Active"
              defaultChecked={selected?.is_active ?? true}
            />
          </div>

          <div className="flex gap-3 self-end sm:col-span-2">
            <button className="inline-flex items-center gap-2 rounded-md bg-emerald-700 px-4 py-2 font-medium text-white shadow-sm hover:bg-emerald-800">
              <ActionIcon name="save" />
              {selected ? 'Save warehouse' : 'Create warehouse'}
            </button>
            <button
              type="button"
              onClick={() => {
                setSelected(null);
                setIsFormOpen(false);
              }}
              className="rounded-md border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      <label className="mt-6 inline-flex items-center gap-2 text-sm text-slate-600">
        <input
          type="checkbox"
          checked={includeInactive}
          onChange={(event) => setIncludeInactive(event.target.checked)}
        />
        Show deleted warehouses
      </label>

      <div className="mt-3 overflow-x-auto rounded-lg border border-slate-200">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-4 py-3">Warehouse</th>
              <th className="px-4 py-3">Code</th>
              <th className="px-4 py-3">Address</th>
              <th className="px-4 py-3">Role</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {warehouses.map((warehouse) => (
              <tr key={warehouse.id} className="hover:bg-slate-50/60">
                <td className="px-4 py-3 font-medium text-slate-900">{warehouse.name}</td>
                <td className="px-4 py-3 font-mono text-xs font-semibold text-slate-800">
                  {warehouse.code}
                </td>
                <td className="px-4 py-3 text-slate-600">{warehouse.address ?? '—'}</td>
                <td className="px-4 py-3">
                  {warehouse.is_default && warehouse.deleted_at === null ? (
                    <span className="rounded bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-800">
                      Default
                    </span>
                  ) : (
                    <span className="text-slate-400">—</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  {warehouse.deleted_at !== null ? (
                    <span className="rounded bg-rose-50 px-2 py-0.5 text-xs font-medium text-rose-700">
                      Deleted
                    </span>
                  ) : warehouse.is_active ? (
                    <span className="rounded bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-800">
                      Active
                    </span>
                  ) : (
                    <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                      Inactive
                    </span>
                  )}
                </td>
                <td className="px-4 py-3">
                  {warehouse.deleted_at === null &&
                    profile?.permissions.includes('master_data.warehouses.update') && (
                      <IconActionButton
                        icon="edit"
                        label={`Edit ${warehouse.name}`}
                        onClick={() => {
                          setErrors({});
                          setSelected(warehouse);
                          setIsFormOpen(true);
                        }}
                        className="mr-1 p-2 text-emerald-800 hover:bg-emerald-50"
                      />
                    )}
                  {warehouse.deleted_at === null &&
                    profile?.permissions.includes('master_data.warehouses.delete') && (
                      <IconActionButton
                        icon="delete"
                        label={`Delete ${warehouse.name}`}
                        onClick={() => void setDeleted(warehouse, true)}
                        className="mr-1 p-2 text-rose-700 hover:bg-rose-50"
                      />
                    )}
                  {warehouse.deleted_at !== null &&
                    profile?.permissions.includes('master_data.warehouses.update') && (
                      <IconActionButton
                        icon="restore"
                        label={`Restore ${warehouse.name}`}
                        onClick={() => void setDeleted(warehouse, false)}
                        className="p-2 text-emerald-800 hover:bg-emerald-50"
                      />
                    )}
                </td>
              </tr>
            ))}
            {warehouses.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                  No warehouses found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default function WarehousesPage() {
  return (
    <ProtectedPage>
      <WarehousesContent />
    </ProtectedPage>
  );
}