'use client';

import { useEffect, useState, type FormEvent } from 'react';
import Image from 'next/image';

import { ProtectedPage } from '@/components/auth/protected-page';
import { useSessionProfile } from '@/components/auth/session-shell';
import { FieldError, RequiredMark, type FieldErrors } from '@/components/forms/field-error';
import { ActionIcon } from '@/components/ui/action-icon';
import { apiRequest, getApiUrl } from '@/lib/auth-api';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';

type CompanySettingRecord = {
  key: string;
  value: string;
};
type BrandAssetType = 'logo' | 'favicon';

type FieldDefinition = {
  key: string;
  label: string;
  type: 'text' | 'email' | 'tel' | 'textarea' | 'select' | 'number';
  options?: { value: string; label: string }[];
  placeholder?: string;
  required?: boolean;
  maxLength?: number;
  minLength?: number;
  min?: string;
  step?: string;
  pattern?: string;
  title?: string;
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
      {
        key: 'company_name',
        label: 'Company name',
        type: 'text',
        placeholder: 'Sabuj Pran',
        required: true,
        maxLength: 255,
      },
      {
        key: 'company_email',
        label: 'Company email',
        type: 'email',
        placeholder: 'info@example.com',
        maxLength: 255,
      },
      {
        key: 'company_phone',
        label: 'Company phone',
        type: 'tel',
        placeholder: '+880...',
        pattern: '\\+?[0-9][0-9 ()-]{5,28}[0-9]',
        title: 'Enter a phone number with 7 to 30 digits.',
      },
      {
        key: 'company_address',
        label: 'Company address',
        type: 'textarea',
        placeholder: 'Street, city, country',
        maxLength: 1000,
      },
    ],
  },
  {
    title: 'Regional settings',
    description: 'Default currency code and timezone for the company.',
    fields: [
      {
        key: 'currency_code',
        label: 'Currency code',
        type: 'text',
        placeholder: 'BDT',
        required: true,
        minLength: 3,
        maxLength: 3,
        pattern: '[A-Za-z]{3}',
        title: 'Enter a three-letter currency code.',
      },
      {
        key: 'timezone',
        label: 'Timezone',
        type: 'text',
        placeholder: 'Asia/Dhaka',
        required: true,
        maxLength: 100,
        pattern: 'UTC|[A-Za-z][A-Za-z0-9._+-]*(/[A-Za-z0-9._+-]+)+',
      },
    ],
  },
  {
    title: 'Invoice settings',
    description: 'Default invoice footer and credit-limit behavior.',
    fields: [
      {
        key: 'invoice_footer',
        label: 'Invoice footer',
        type: 'textarea',
        placeholder: 'Thank you for your business',
        maxLength: 1000,
      },
      {
        key: 'credit_limit_mode',
        label: 'Credit limit mode',
        type: 'select',
        options: [
          { value: 'WARN', label: 'Warn only' },
          { value: 'BLOCK', label: 'Block order/invoice' },
        ],
        required: true,
      },
    ],
  },
  {
    title: 'Purchase settings',
    description: 'Default tolerance for goods received above the ordered quantity.',
    fields: [
      {
        key: 'receipt_tolerance_pct',
        label: 'Receiving tolerance (%)',
        type: 'number',
        placeholder: '0',
        required: true,
        min: '0',
        step: '0.01',
      },
    ],
  },
];

const brandAssets: {
  type: BrandAssetType;
  key: string;
  label: string;
  description: string;
  defaultValue: string;
  accept: string;
}[] = [
  {
    type: 'logo',
    key: 'company_logo_path',
    label: 'Company logo',
    description: 'PNG, JPEG, or WebP image up to 2 MB.',
    defaultValue: '/brand/company-logo.svg',
    accept: 'image/png,image/jpeg,image/webp',
  },
  {
    type: 'favicon',
    key: 'company_favicon_path',
    label: 'Favicon',
    description: 'PNG, WebP, or ICO image up to 512 KB.',
    defaultValue: '/brand/favicon.svg',
    accept: 'image/png,image/webp,image/x-icon',
  },
];

function CompanySettingsContent() {
  const profile = useSessionProfile();
  const [values, setValues] = useState<Record<string, string>>({});
  const [errors, setErrors] = useState<FieldErrors>({});
  const [loaded, setLoaded] = useState(false);
  const [savingGroup, setSavingGroup] = useState<string | null>(null);
  const [savingAsset, setSavingAsset] = useState<BrandAssetType | null>(null);

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

  useEffect(() => {
    const favicon = values.company_favicon_path;
    if (!favicon) return;
    let link = document.querySelector<HTMLLinkElement>('link[rel~="icon"]');
    if (!link) {
      link = document.createElement('link');
      link.rel = 'icon';
      document.head.append(link);
    }
    link.href = getAssetUrl(favicon);
  }, [values.company_favicon_path]);

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

  async function uploadAsset(type: BrandAssetType, file: File | undefined) {
    if (!file || !profile?.permissions.includes('master_data.company_settings.update')) return;
    setSavingAsset(type);
    try {
      const record = await apiRequest<CompanySettingRecord>(
        `/api/v1/company-settings/assets/${type}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': file.type },
          body: file,
        },
      );
      setValues((current) => ({ ...current, [record.key]: record.value }));
      showSuccessToast(`${type === 'logo' ? 'Company logo' : 'Favicon'} updated.`);
    } catch (cause) {
      showErrorToast(
        cause instanceof Error
          ? cause.message
          : `Could not upload ${type === 'logo' ? 'company logo' : 'favicon'}`,
      );
    } finally {
      setSavingAsset(null);
    }
  }

  async function restoreAssetDefault(asset: (typeof brandAssets)[number]) {
    if (!profile?.permissions.includes('master_data.company_settings.update')) return;
    setSavingAsset(asset.type);
    try {
      await apiRequest<CompanySettingRecord>(
        `/api/v1/company-settings/${encodeURIComponent(asset.key)}`,
        {
          method: 'PUT',
          body: JSON.stringify({ value: asset.defaultValue }),
        },
      );
      setValues((current) => ({ ...current, [asset.key]: asset.defaultValue }));
      showSuccessToast(`${asset.label} restored to default.`);
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : `Could not restore ${asset.label.toLowerCase()}`);
    } finally {
      setSavingAsset(null);
    }
  }

  function handleChange(key: string, value: string) {
    setValues((current) => ({ ...current, [key]: value }));
    setErrors((current) => {
      if (!current[key]) return current;
      const next = { ...current };
      delete next[key];
      return next;
    });
  }

  function handleInvalid(event: FormEvent<HTMLFormElement>) {
    const field = event.target;
    if (
      (field instanceof HTMLInputElement ||
        field instanceof HTMLTextAreaElement ||
        field instanceof HTMLSelectElement) &&
      field.name
    ) {
      setErrors((current) => ({ ...current, [field.name]: field.validationMessage }));
    }
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

      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4">
          <h2 className="text-lg font-semibold text-slate-900">Brand assets</h2>
          <p className="mt-1 text-sm text-slate-500">
            Upload the logo and favicon used by the workspace. Default Sabuj Pran artwork is
            selected until you replace it.
          </p>
        </div>
        <div className="grid gap-6 md:grid-cols-2">
          {brandAssets.map((asset) => (
            <div key={asset.type} className="rounded-lg border border-slate-200 p-4">
              <div className="mb-3 flex min-h-20 items-center justify-center rounded-md bg-slate-50 p-3">
                <Image
                  src={getAssetUrl(values[asset.key] || asset.defaultValue)}
                  alt={`${asset.label} preview`}
                  width={asset.type === 'logo' ? 240 : 48}
                  height={asset.type === 'logo' ? 64 : 48}
                  unoptimized
                  className={
                    asset.type === 'logo'
                      ? 'max-h-16 max-w-full object-contain'
                      : 'h-12 w-12 object-contain'
                  }
                />
              </div>
              <label className="block text-sm font-medium text-slate-800">
                {asset.label}
                <input
                  type="file"
                  accept={asset.accept}
                  disabled={!canUpdate || savingAsset === asset.type}
                  className="mt-2 block w-full text-sm text-slate-700 file:mr-3 file:rounded-md file:border-0 file:bg-emerald-50 file:px-3 file:py-2 file:font-medium file:text-emerald-800 hover:file:bg-emerald-100 disabled:opacity-60"
                  onChange={(event) => {
                    void uploadAsset(asset.type, event.currentTarget.files?.[0]);
                    event.currentTarget.value = '';
                  }}
                />
              </label>
              <p className="mt-2 text-xs text-slate-500">{asset.description}</p>
              {canUpdate && (
                <button
                  type="button"
                  disabled={savingAsset === asset.type}
                  onClick={() => void restoreAssetDefault(asset)}
                  className="mt-3 text-sm font-medium text-emerald-800 underline underline-offset-2 disabled:opacity-60"
                >
                  Use default
                </button>
              )}
            </div>
          ))}
        </div>
      </section>

      {groups.map((group) => (
        <section key={group.title} className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-4">
            <h2 className="text-lg font-semibold text-slate-900">{group.title}</h2>
            <p className="mt-1 text-sm text-slate-500">{group.description}</p>
          </div>

          <form
            className="grid gap-4 sm:grid-cols-2"
            onSubmit={handleSubmit(group)}
            onInvalidCapture={handleInvalid}
          >
            {group.fields.map((field) => (
              <div
                key={field.key}
                className={`block text-sm font-medium ${field.type === 'textarea' ? 'sm:col-span-2' : ''}`}
              >
                <label htmlFor={field.key}>
                  {field.label}
                  {field.required && <RequiredMark />}
                </label>
                <FieldInput
                  field={field}
                  value={values[field.key] ?? ''}
                  disabled={!canUpdate}
                  error={errors[field.key]}
                  onChange={(value) => handleChange(field.key, value)}
                />
                <FieldError id={`${field.key}-error`} message={errors[field.key]} />
              </div>
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

function getAssetUrl(path: string): string {
  return path.startsWith('/media/') ? getApiUrl(path) : path;
}

function FieldInput({
  field,
  value,
  disabled,
  error,
  onChange,
}: {
  field: FieldDefinition;
  value: string;
  disabled: boolean;
  error?: string;
  onChange: (value: string) => void;
}) {
  const className =
    `mt-1 w-full rounded-md border px-3 py-2 focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-100 ${
      error ? 'border-rose-500' : 'border-slate-300'
    }`;

  if (field.type === 'textarea') {
    return (
      <textarea
        id={field.key}
        name={field.key}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={4}
        disabled={disabled}
        required={field.required}
        placeholder={field.placeholder}
        maxLength={field.maxLength}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${field.key}-error` : undefined}
        className={className}
      />
    );
  }

  if (field.type === 'select') {
    return (
      <select
        id={field.key}
        name={field.key}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        required={field.required}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${field.key}-error` : undefined}
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
      id={field.key}
      name={field.key}
      type={field.type}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      disabled={disabled}
      placeholder={field.placeholder}
      required={field.required}
      maxLength={field.maxLength}
      minLength={field.minLength}
      min={field.min}
      step={field.step}
      pattern={field.pattern}
      title={field.title}
      aria-invalid={Boolean(error)}
      aria-describedby={error ? `${field.key}-error` : undefined}
      onBlur={field.key === 'currency_code' ? (event) => onChange(event.target.value.toUpperCase()) : undefined}
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