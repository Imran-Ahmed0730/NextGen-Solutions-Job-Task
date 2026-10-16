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
import { paymentMethodSchema } from '@/lib/auth-validation';

type PaymentMethodRecord = {
  id: number;
  name: string;
  type: 'CASH' | 'BANK' | 'MFS' | 'ONLINE';
  is_active: boolean;
  deleted_at: string | null;
};

const typeLabels: Record<PaymentMethodRecord['type'], string> = {
  CASH: 'Cash',
  BANK: 'Bank',
  MFS: 'Mobile Financial Service',
  ONLINE: 'Online',
};

function PaymentMethodsContent() {
  const profile = useSessionProfile();
  const [methods, setMethods] = useState<PaymentMethodRecord[]>([]);
  const [selected, setSelected] = useState<PaymentMethodRecord | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [includeInactive, setIncludeInactive] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});

  async function reload() {
    const query = includeInactive ? '?include_inactive=true' : '';
    setMethods(await apiRequest<PaymentMethodRecord[]>(`/api/v1/payment-methods${query}`));
  }

  useEffect(() => {
    reload().catch((cause: unknown) =>
      showErrorToast(cause instanceof Error ? cause.message : 'Could not load payment methods'),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [includeInactive]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const parsed = paymentMethodSchema.safeParse({
      name: form.get('name'),
      type: form.get('type'),
      is_active: form.get('is_active') === 'on',
    });
    if (!parsed.success) {
      setErrors(getFieldErrors(parsed.error.issues));
      return;
    }
    setErrors({});

    try {
      await apiRequest<PaymentMethodRecord>(
        selected ? `/api/v1/payment-methods/${selected.id}` : '/api/v1/payment-methods',
        {
          method: selected ? 'PATCH' : 'POST',
          body: JSON.stringify(parsed.data),
        },
      );
      showSuccessToast(selected ? 'Payment method updated.' : 'Payment method created.');
      setSelected(null);
      setIsFormOpen(false);
    } catch (cause) {
      const apiErrors = getApiFieldErrors(cause);
      if (Object.keys(apiErrors).length) setErrors(apiErrors);
      else showErrorToast(cause instanceof Error ? cause.message : 'Could not save payment method');
      return;
    }
    try {
      await reload();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not refresh payment methods');
    }
  }

  async function setDeleted(method: PaymentMethodRecord, deleteAction: boolean) {
    if (deleteAction) {
      const confirmation = await Swal.fire({
        title: 'Delete payment method?',
        text: `Are you sure you want to delete "${method.name}"?`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#b91c1c',
        cancelButtonColor: '#64748b',
        confirmButtonText: 'Yes, delete',
      });
      if (!confirmation.isConfirmed) return;
    }
    try {
      await apiRequest<PaymentMethodRecord>(
        deleteAction
          ? `/api/v1/payment-methods/${method.id}`
          : `/api/v1/payment-methods/${method.id}/activate`,
        { method: deleteAction ? 'DELETE' : 'POST' },
      );
      showSuccessToast(deleteAction ? 'Payment method deleted.' : 'Payment method restored.');
    } catch (cause) {
      showErrorToast(
        cause instanceof Error ? cause.message : 'Could not update payment method status',
      );
      return;
    }
    try {
      await reload();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not refresh payment methods');
    }
  }

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Payment Methods</h1>
          <p className="mt-1 text-sm text-slate-600">
            Define how money is received and paid out across the business.
          </p>
        </div>
        {profile?.permissions.includes('master_data.payment_methods.create') && !isFormOpen && (
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
            Add payment method
          </button>
        )}
      </div>

      {isFormOpen && (
        <form
          key={selected?.id ?? 'new-payment-method'}
          noValidate
          className="mt-6 grid max-w-3xl gap-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm sm:grid-cols-2"
          onSubmit={submit}
        >
          <label className="block text-sm font-medium">
            Name<RequiredMark />
            <input type="text"
              name="name"
              placeholder="e.g. Cash"
              defaultValue={selected?.name ?? ''}
              minLength={1}
              maxLength={100}
              required
              aria-invalid={Boolean(errors.name)}
              aria-describedby={errors.name ? 'payment-method-name-error' : undefined}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            />
            <FieldError id="payment-method-name-error" message={errors.name} />
          </label>

          <label className="block text-sm font-medium">
            Type<RequiredMark />
            <select
              name="type"
              defaultValue={selected?.type ?? 'CASH'}
              required
              aria-invalid={Boolean(errors.type)}
              aria-describedby={errors.type ? 'payment-method-type-error' : undefined}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            >
              <option value="CASH">Cash</option>
              <option value="BANK">Bank</option>
              <option value="MFS">Mobile Financial Service</option>
              <option value="ONLINE">Online</option>
            </select>
            <FieldError id="payment-method-type-error" message={errors.type} />
          </label>

          <div className="flex flex-col justify-center space-y-3 sm:col-span-2">
            <StatusSwitch
              name="is_active"
              label="Active"
              defaultChecked={selected?.is_active ?? true}
            />
          </div>

          <div className="flex gap-3 self-end sm:col-span-2">
            <button className="inline-flex items-center gap-2 rounded-md bg-emerald-700 px-4 py-2 font-medium text-white shadow-sm hover:bg-emerald-800">
              <ActionIcon name="save" />
              {selected ? 'Save payment method' : 'Create payment method'}
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
        Show deleted payment methods
      </label>

      <div className="mt-3 overflow-x-auto rounded-lg border border-slate-200">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {methods.map((method) => (
              <tr key={method.id} className="hover:bg-slate-50/60">
                <td className="px-4 py-3 font-medium text-slate-900">{method.name}</td>
                <td className="px-4 py-3 text-slate-600">{typeLabels[method.type]}</td>
                <td className="px-4 py-3">
                  {method.deleted_at !== null ? (
                    <span className="rounded bg-rose-50 px-2 py-0.5 text-xs font-medium text-rose-700">
                      Deleted
                    </span>
                  ) : method.is_active ? (
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
                  {method.deleted_at === null &&
                    profile?.permissions.includes('master_data.payment_methods.update') && (
                      <IconActionButton
                        icon="edit"
                        label={`Edit ${method.name}`}
                        onClick={() => {
                          setErrors({});
                          setSelected(method);
                          setIsFormOpen(true);
                        }}
                        className="mr-1 p-2 text-emerald-800 hover:bg-emerald-50"
                      />
                    )}
                  {method.deleted_at === null &&
                    profile?.permissions.includes('master_data.payment_methods.delete') && (
                      <IconActionButton
                        icon="delete"
                        label={`Delete ${method.name}`}
                        onClick={() => void setDeleted(method, true)}
                        className="mr-1 p-2 text-rose-700 hover:bg-rose-50"
                      />
                    )}
                  {method.deleted_at !== null &&
                    profile?.permissions.includes('master_data.payment_methods.update') && (
                      <IconActionButton
                        icon="restore"
                        label={`Restore ${method.name}`}
                        onClick={() => void setDeleted(method, false)}
                        className="p-2 text-emerald-800 hover:bg-emerald-50"
                      />
                    )}
                </td>
              </tr>
            ))}
            {methods.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-slate-500">
                  No payment methods found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default function PaymentMethodsPage() {
  return (
    <ProtectedPage>
      <PaymentMethodsContent />
    </ProtectedPage>
  );
}