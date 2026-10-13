'use client';

import { useEffect, useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { useSessionProfile } from '@/components/auth/session-shell';
import {
  FieldError,
  getApiFieldErrors,
  getFieldErrors,
  RequiredMark,
  type FieldErrors,
} from '@/components/forms/field-error';
import { apiRequest } from '@/lib/auth-api';
import { unitSchema } from '@/lib/auth-validation';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';
import { ActionIcon, IconActionButton } from '@/components/ui/action-icon';

type UnitRecord = {
  id: number;
  name: string;
  code: string;
  allow_decimal: boolean;
  is_active: boolean;
  deleted_at: string | null;
};

function UnitsContent() {
  const profile = useSessionProfile();
  const [units, setUnits] = useState<UnitRecord[]>([]);
  const [selected, setSelected] = useState<UnitRecord | null>(null);
  const [includeInactive, setIncludeInactive] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});

  useEffect(() => {
    const query = includeInactive ? '?include_inactive=true' : '';
    apiRequest<UnitRecord[]>(`/api/v1/units${query}`)
      .then(setUnits)
      .catch((cause: unknown) =>
        showErrorToast(cause instanceof Error ? cause.message : 'Could not load units'),
      );
  }, [includeInactive]);

  async function reload() {
    const query = includeInactive ? '?include_inactive=true' : '';
    setUnits(await apiRequest<UnitRecord[]>(`/api/v1/units${query}`));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const parsed = unitSchema.safeParse({
      name: form.get('name'),
      code: form.get('code'),
      allow_decimal: form.get('allow_decimal') === 'on',
    });
    if (!parsed.success) {
      setErrors(getFieldErrors(parsed.error.issues));
      return;
    }
    setErrors({});

    try {
      await apiRequest<UnitRecord>(
        selected ? `/api/v1/units/${selected.id}` : '/api/v1/units',
        {
          method: selected ? 'PATCH' : 'POST',
          body: JSON.stringify(parsed.data),
        },
      );
      showSuccessToast(selected ? 'Unit updated.' : 'Unit created.');
      setSelected(null);
    } catch (cause) {
      const apiErrors = getApiFieldErrors(cause);
      if (Object.keys(apiErrors).length) setErrors(apiErrors);
      else showErrorToast(cause instanceof Error ? cause.message : 'Could not save unit');
      return;
    }
    try {
      await reload();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not refresh the unit list');
    }
  }

  async function setActive(unit: UnitRecord, active: boolean) {
    try {
      await apiRequest<UnitRecord>(
        active ? `/api/v1/units/${unit.id}/activate` : `/api/v1/units/${unit.id}`,
        { method: active ? 'POST' : 'DELETE' },
      );
      showSuccessToast(active ? 'Unit restored.' : 'Unit deleted.');
      if (selected?.id === unit.id) setSelected(null);
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not update unit');
      return;
    }
    try {
      await reload();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not refresh the unit list');
    }
  }

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Units</h1>
          <p className="mt-1 text-sm text-slate-600">Manage measurement units used by products.</p>
        </div>
        {profile?.permissions.includes('master_data.units.create') && (
          <button
            type="button"
            onClick={() => {
              setErrors({});
              setSelected(null);
            }}
            className="inline-flex items-center gap-2 rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white"
          >
            <ActionIcon name="add" />
            Add unit
          </button>
        )}
      </div>

      {(selected
        ? profile?.permissions.includes('master_data.units.update')
        : profile?.permissions.includes('master_data.units.create')) && (
        <form
          key={selected?.id ?? 'new-unit'}
          noValidate
          className="mt-6 grid max-w-3xl gap-4 rounded-lg border border-slate-200 p-4 sm:grid-cols-2"
          onSubmit={submit}
        >
          <label className="block text-sm font-medium">
            Unit name<RequiredMark />
            <input
              name="name"
              placeholder="e.g. Kilogram"
              defaultValue={selected?.name ?? ''}
              minLength={1}
              maxLength={100}
              required
              aria-invalid={Boolean(errors.name)}
              aria-describedby={errors.name ? 'unit-name-error' : undefined}
              className="mt-1 w-full rounded-md border px-3 py-2"
            />
            <FieldError id="unit-name-error" message={errors.name} />
          </label>
          <label className="block text-sm font-medium">
            Unit code<RequiredMark />
            <input
              name="code"
              placeholder="e.g. kg"
              defaultValue={selected?.code ?? ''}
              minLength={1}
              maxLength={30}
              required
              aria-invalid={Boolean(errors.code)}
              aria-describedby={errors.code ? 'unit-code-error' : undefined}
              className="mt-1 w-full rounded-md border px-3 py-2"
            />
            <FieldError id="unit-code-error" message={errors.code} />
          </label>
          <label className="flex items-center gap-2 text-sm sm:col-span-2">
            <input
              name="allow_decimal"
              type="checkbox"
              defaultChecked={selected?.allow_decimal ?? false}
              className="rounded border-slate-300"
            />
            Allow fractional quantities
          </label>
          <div className="flex gap-3 sm:col-span-2">
            <button className="inline-flex items-center gap-2 rounded-md bg-emerald-700 px-4 py-2 font-medium text-white">
              <ActionIcon name="save" />
              {selected ? 'Save unit' : 'Create unit'}
            </button>
            {selected && (
              <button
                type="button"
                onClick={() => setSelected(null)}
                className="rounded-md border border-slate-300 px-4 py-2"
              >
                Cancel
              </button>
            )}
          </div>
        </form>
      )}

      <label className="mt-6 inline-flex items-center gap-2 text-sm text-slate-600">
        <input
          type="checkbox"
          checked={includeInactive}
          onChange={(event) => setIncludeInactive(event.target.checked)}
        />
        Show deleted units
      </label>

      <div className="mt-3 overflow-x-auto rounded-lg border border-slate-200">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-4 py-3">Unit</th>
              <th className="px-4 py-3">Code</th>
              <th className="px-4 py-3">Quantity format</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {units.map((unit) => (
              <tr key={unit.id}>
                <td className="px-4 py-3 font-medium">{unit.name}</td>
                <td className="px-4 py-3 font-mono">{unit.code}</td>
                <td className="px-4 py-3">{unit.allow_decimal ? 'Fractional' : 'Whole'}</td>
                <td className="px-4 py-3">{unit.is_active ? 'Active' : 'Deleted'}</td>
                <td className="space-x-3 px-4 py-3">
                  {unit.is_active && profile?.permissions.includes('master_data.units.update') && (
                    <IconActionButton
                      icon="edit"
                      label={`Edit ${unit.name}`}
                      onClick={() => {
                        setErrors({});
                        setSelected(unit);
                      }}
                      className="mr-1 p-2 text-emerald-800 hover:bg-emerald-50"
                    />
                  )}
                  {unit.is_active && profile?.permissions.includes('master_data.units.delete') && (
                    <IconActionButton
                      icon="delete"
                      label={`Delete ${unit.name}`}
                      onClick={() => void setActive(unit, false)}
                      className="mr-1 p-2 text-rose-700 hover:bg-rose-50"
                    />
                  )}
                  {!unit.is_active && profile?.permissions.includes('master_data.units.update') && (
                    <IconActionButton
                      icon="restore"
                      label={`Restore ${unit.name}`}
                      onClick={() => void setActive(unit, true)}
                      className="p-2 text-emerald-800 hover:bg-emerald-50"
                    />
                  )}
                </td>
              </tr>
            ))}
            {units.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                  No units found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default function UnitsPage() {
  return (
    <ProtectedPage>
      <UnitsContent />
    </ProtectedPage>
  );
}
