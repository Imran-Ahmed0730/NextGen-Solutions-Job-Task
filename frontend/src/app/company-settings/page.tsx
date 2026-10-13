'use client';

import { useEffect, useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { useSessionProfile } from '@/components/auth/session-shell';
import { ActionIcon } from '@/components/ui/action-icon';
import { apiRequest } from '@/lib/auth-api';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';

type CompanySettingRecord = {
  key: string;
  value: string;
};

type FieldDefinition = {
  key: string;
  label: string;
  type: 'text' | 'email' | 'tel' | 'textarea' | 'select' | 'number';
  options?: { value: string; label: string }[];
  placeholder?: string;
};

type SettingsGroup = {
  title: string;
  description: string;
  fields: FieldDefinition[];
};

const groups: SettingsGroup[] = [
  {
    title: 'Company profile',
    description: 'Basic details shown on documents and reports.',
    fields: [
      { key: 'company_name', label: 'Company name', type: 'text', placeholder: 'Sabuj Pran' },
      { key: 'company_email', label: 'Company email', type: 'email', placeholder: 'info@example.com' },
      { key: 'company_phone', label: 'Company phone', type: 'tel', placeholder: '+880...' },
      { key: 'company_address', label: 'Company address', type: 'textarea', placeholder: 'Street, city, country' },
    ],
  },
  {
    title: 'Regional settings',
    description: 'Currency and timezone used for display and calculations.',
    fields: [
      { key: 'currency_code', label: 'Currency code', type: 'text', placeholder: 'BDT' },
      { key: 'timezone', label: 'Timezone', type: 'text', placeholder: 'Asia/Dhaka' },
    ],
  },
  {
    title: 'Sales and billing',
    description: 'Invoice notes and credit-control defaults.',
    fields: [
      { key: 'invoice_footer', label: 'Invoice footer', type: 'textarea', placeholder: 'Thank you for your business' },
      {
        key: 'credit_limit_mode',
        label: 'Credit limit mode',
        type: 'select',
        options: [
          { value: 'WARN', label: 'Warn only' },
          { value: 'BLOCK', label: 'Block order/invoice' },
        ],
      },
      {
        key: 'receipt_tolerance_pct',
        label: 'Receiving tolerance (%)',
        type: 'number',
        placeholder: '0',
      },
    ],
  },
];

function CompanySettingsContent() {
  const profile = useSessionProfile();
  const [values, setValues] = useState<Record<string, string>>({});
  const [loaded, setLoaded] = useState(false);
  const [savingGroup, setSavingGroup] = useState<string | null>(null);

  async function reload() {
    const records = await apiRequest<CompanySettingRecord[]>('/api/v1/company-settings');
    const next: Record<string, string> = {};
    for (const record of records) next[record.key] = record.value;
    setValues(next);
    setLoaded(true);
  }

  useEffect(() => {
    reload().catch((cause: unknown) =>
      showErrorToast(cause instanceof Error ? cause.message : 'Could not load company settings'),
    );
  }, []);

  async function saveGroup(group: SettingsGroup, form: HTMLFormElement) {
    if (!profile?.permissions.includes('master_data.company_settings.update')) return;
    setSavingGroup(group.title);
    const data = new FormData(form);
    const updates = group.fields.map((field) => ({
      key: field.key,
      value: String(data.get(field.key) ?? ''),
    }));

    try {
      await Promise.all(
        updates.map((item) =>
          apiRequest<CompanySettingRecord>(
            `/api/v1/company-settings/${encodeURIComponent(item.key)}`,
            {
              method: 'PUT',
              body: JSON.stringify({ key: item.key, value: item.value }),
            },
          ),
        ),
      );
      setValues((current) => {
        const next = { ...current };
        for (const item of updates) next[item.key] = item.value;
        return next;
      });
      showSuccessToast(`${group.title} saved.`);
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : `Could not save ${group.title.toLowerCase()}`);
    } finally {
      setSavingGroup(null);
    }
  }

  function handleChange(key: string, value: string) {
    setValues((current) => ({ ...current, [key]: value }));
  }

  function handleSubmit(group: SettingsGroup) {
    return (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      saveGroup(group, event.currentTarget);
    };
  }

  if (!loaded) {
    return (
      <section className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500 shadow-sm">
        Loading company settings...
      </section>
    );
  }

  const canUpdate = profile?.permissions.includes('master_data.company_settings.update') ?? false;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Company Settings</h1>
        <p className="mt-1 text-sm text-slate-600">
          Manage company information and defaults in organized sections.
        </p>
      </div>

      {groups.map((group) => (
        <section key={group.title} className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-4">
            <h2 className="text-lg font-semibold text-slate-900">{group.title}</h2>
            <p className="mt-1 text-sm text-slate-500">{group.description}</p>
          </div>

          <form className="grid gap-4 sm:grid-cols-2" onSubmit={handleSubmit(group)}>
            {group.fields.map((field) => (
              <label
                key={field.key}
                className={`block text-sm font-medium ${field.type === 'textarea' ? 'sm:col-span-2' : ''}`}
              >
                {field.label}
                <FieldInput
                  field={field}
                  value={values[field.key] ?? ''}
                  disabled={!canUpdate}
                  onChange={(value) => handleChange(field.key, value)}
                />
              </label>
            ))}

            {canUpdate && (
              <div className="sm:col-span-2">
                <button
                  type="submit"
                  disabled={savingGroup === group.title}
                  className="inline-flex items-center gap-2 rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <ActionIcon name="save" />
                  {savingGroup === group.title ? 'Saving...' : `Save ${group.title}`}
                </button>
              </div>
            )}
          </form>
        </section>
      ))}
    </div>
  );
}

function FieldInput({
  field,
  value,
  disabled,
  onChange,
}: {
  field: FieldDefinition;
  value: string;
  disabled: boolean;
  onChange: (value: string) => void;
}) {
  const className =
    'mt-1 w-full rounded-md border border-slate-300 px-3 py-2 focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-100';

  if (field.type === 'textarea') {
    return (
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={4}
        disabled={disabled}
        placeholder={field.placeholder}
        className={className}
      />
    );
  }

  if (field.type === 'select') {
    return (
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        className={className}
      >
        {(field.options ?? []).map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    );
  }

  return (
    <input
      type={field.type}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      disabled={disabled}
      placeholder={field.placeholder}
      className={className}
    />
  );
}

export default function CompanySettingsPage() {
  return (
    <ProtectedPage>
      <CompanySettingsContent />
    </ProtectedPage>
  );
}