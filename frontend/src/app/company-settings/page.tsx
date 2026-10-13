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
import { ActionIcon, IconActionButton } from '@/components/ui/action-icon';
import { apiRequest } from '@/lib/auth-api';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';
import { companySettingSchema } from '@/lib/auth-validation';

type CompanySettingRecord = {
  key: string;
  value: string;
};

function CompanySettingsContent() {
  const profile = useSessionProfile();
  const [settings, setSettings] = useState<CompanySettingRecord[]>([]);
  const [selected, setSelected] = useState<CompanySettingRecord | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});

  async function reload() {
    setSettings(await apiRequest<CompanySettingRecord[]>('/api/v1/company-settings'));
  }

  useEffect(() => {
    reload().catch((cause: unknown) =>
      showErrorToast(cause instanceof Error ? cause.message : 'Could not load company settings'),
    );
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const parsed = companySettingSchema.safeParse({
      key: form.get('key'),
      value: form.get('value'),
    });
    if (!parsed.success) {
      setErrors(getFieldErrors(parsed.error.issues));
      return;
    }
    setErrors({});

    const isNew = selected === null;
    try {
      await apiRequest<CompanySettingRecord>(
        isNew ? '/api/v1/company-settings' : `/api/v1/company-settings/${encodeURIComponent(selected.key)}`,
        {
          method: isNew ? 'POST' : 'PATCH',
          body: JSON.stringify(parsed.data),
        },
      );
      showSuccessToast(isNew ? 'Setting created.' : 'Setting updated.');
      setSelected(null);
      setIsFormOpen(false);
    } catch (cause) {
      const apiErrors = getApiFieldErrors(cause);
      if (Object.keys(apiErrors).length) setErrors(apiErrors);
      else showErrorToast(cause instanceof Error ? cause.message : 'Could not save company setting');
      return;
    }
    try {
      await reload();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not refresh company settings');
    }
  }

  async function deleteSetting(setting: CompanySettingRecord) {
    const confirmation = await Swal.fire({
      title: 'Delete setting?',
      text: `Are you sure you want to delete "${setting.key}"?`,
      icon: 'warning',
      showCancelButton: true,
      confirmButtonColor: '#b91c1c',
      cancelButtonColor: '#64748b',
      confirmButtonText: 'Yes, delete',
    });
    if (!confirmation.isConfirmed) return;
    try {
      await apiRequest<void>(
        `/api/v1/company-settings/${encodeURIComponent(setting.key)}`,
        { method: 'DELETE' },
      );
      showSuccessToast('Setting deleted.');
      await reload();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not delete company setting');
    }
  }

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Company Settings</h1>
          <p className="mt-1 text-sm text-slate-600">
            Store flexible company configuration as key/value pairs.
          </p>
        </div>
        {profile?.permissions.includes('master_data.company_settings.create') && !isFormOpen && (
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
            Add setting
          </button>
        )}
      </div>

      {isFormOpen && (
        <form
          key={selected?.key ?? 'new-company-setting'}
          noValidate
          className="mt-6 grid max-w-3xl gap-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
          onSubmit={submit}
        >
          <label className="block text-sm font-medium">
            Key<RequiredMark />
            <input
              name="key"
              placeholder="e.g. company_name"
              defaultValue={selected?.key ?? ''}
              minLength={1}
              maxLength={100}
              required
              readOnly={selected !== null}
              aria-invalid={Boolean(errors.key)}
              aria-describedby={errors.key ? 'company-setting-key-error' : undefined}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            />
            <FieldError id="company-setting-key-error" message={errors.key} />
          </label>

          <label className="block text-sm font-medium">
            Value
            <textarea
              name="value"
              placeholder="Setting value"
              defaultValue={selected?.value ?? ''}
              rows={4}
              aria-invalid={Boolean(errors.value)}
              aria-describedby={errors.value ? 'company-setting-value-error' : undefined}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            />
            <FieldError id="company-setting-value-error" message={errors.value} />
          </label>

          <div className="flex gap-3 self-end">
            <button className="inline-flex items-center gap-2 rounded-md bg-emerald-700 px-4 py-2 font-medium text-white shadow-sm hover:bg-emerald-800">
              <ActionIcon name="save" />
              {selected ? 'Save setting' : 'Create setting'}
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

      <div className="mt-6 overflow-x-auto rounded-lg border border-slate-200">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-4 py-3">Key</th>
              <th className="px-4 py-3">Value</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {settings.map((setting) => (
              <tr key={setting.key} className="hover:bg-slate-50/60">
                <td className="px-4 py-3 font-medium text-slate-900">{setting.key}</td>
                <td className="px-4 py-3 text-slate-600">
                  <span className="whitespace-pre-wrap">{setting.value}</span>
                </td>
                <td className="px-4 py-3">
                  {profile?.permissions.includes('master_data.company_settings.update') && (
                    <IconActionButton
                      icon="edit"
                      label={`Edit ${setting.key}`}
                      onClick={() => {
                        setErrors({});
                        setSelected(setting);
                        setIsFormOpen(true);
                      }}
                      className="mr-1 p-2 text-emerald-800 hover:bg-emerald-50"
                    />
                  )}
                  {profile?.permissions.includes('master_data.company_settings.delete') && (
                    <IconActionButton
                      icon="delete"
                      label={`Delete ${setting.key}`}
                      onClick={() => void deleteSetting(setting)}
                      className="p-2 text-rose-700 hover:bg-rose-50"
                    />
                  )}
                </td>
              </tr>
            ))}
            {settings.length === 0 && (
              <tr>
                <td colSpan={3} className="px-4 py-8 text-center text-slate-500">
                  No company settings found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default function CompanySettingsPage() {
  return (
    <ProtectedPage>
      <CompanySettingsContent />
    </ProtectedPage>
  );
}