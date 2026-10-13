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
import { moneyAccountSchema } from '@/lib/auth-validation';

type MoneyAccountType = 'CASH' | 'BANK' | 'MFS';

type MoneyAccountRecord = {
  id: number;
  name: string;
  type: MoneyAccountType;
  payment_method_id: number | null;
  account_no: string | null;
  opening_balance: string;
  allow_overdraft: boolean;
  is_active: boolean;
  deleted_at: string | null;
};

type PaymentMethodRecord = {
  id: number;
  name: string;
  is_active: boolean;
  deleted_at: string | null;
};

const typeLabels: Record<MoneyAccountType, string> = {
  CASH: 'Cash',
  BANK: 'Bank',
  MFS: 'Mobile Financial Service',
};

function formatAmount(value: string): string {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return value;
  return parsed.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function MoneyAccountsContent() {
  const profile = useSessionProfile();
  const [accounts, setAccounts] = useState<MoneyAccountRecord[]>([]);
  const [methods, setMethods] = useState<PaymentMethodRecord[]>([]);
  const [selected, setSelected] = useState<MoneyAccountRecord | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [includeInactive, setIncludeInactive] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});

  async function reload() {
    const query = includeInactive ? '?include_inactive=true' : '';
    const [accountList, methodList] = await Promise.all([
      apiRequest<MoneyAccountRecord[]>(`/api/v1/money-accounts${query}`),
      apiRequest<PaymentMethodRecord[]>('/api/v1/payment-methods'),
    ]);
    setAccounts(accountList);
    setMethods(methodList);
  }

  useEffect(() => {
    reload().catch((cause: unknown) =>
      showErrorToast(cause instanceof Error ? cause.message : 'Could not load money accounts'),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [includeInactive]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const rawMethodId = form.get('payment_method_id');
    const parsed = moneyAccountSchema.safeParse({
      name: form.get('name'),
      type: form.get('type'),
      payment_method_id: rawMethodId ? Number(rawMethodId) : null,
      account_no: form.get('account_no') || null,
      opening_balance: form.get('opening_balance'),
      allow_overdraft: form.get('allow_overdraft') === 'on',
      is_active: form.get('is_active') === 'on',
    });
    if (!parsed.success) {
      setErrors(getFieldErrors(parsed.error.issues));
      return;
    }
    setErrors({});

    try {
      await apiRequest<MoneyAccountRecord>(
        selected ? `/api/v1/money-accounts/${selected.id}` : '/api/v1/money-accounts',
        {
          method: selected ? 'PATCH' : 'POST',
          body: JSON.stringify(parsed.data),
        },
      );
      showSuccessToast(selected ? 'Money account updated.' : 'Money account created.');
      setSelected(null);
      setIsFormOpen(false);
    } catch (cause) {
      const apiErrors = getApiFieldErrors(cause);
      if (Object.keys(apiErrors).length) setErrors(apiErrors);
      else showErrorToast(cause instanceof Error ? cause.message : 'Could not save money account');
      return;
    }
    try {
      await reload();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not refresh money accounts');
    }
  }

  async function setDeleted(account: MoneyAccountRecord, deleteAction: boolean) {
    if (deleteAction) {
      const confirmation = await Swal.fire({
        title: 'Delete money account?',
        text: `Are you sure you want to delete "${account.name}"?`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#b91c1c',
        cancelButtonColor: '#64748b',
        confirmButtonText: 'Yes, delete',
      });
      if (!confirmation.isConfirmed) return;
    }
    try {
      await apiRequest<MoneyAccountRecord>(
        deleteAction
          ? `/api/v1/money-accounts/${account.id}`
          : `/api/v1/money-accounts/${account.id}/activate`,
        { method: deleteAction ? 'DELETE' : 'POST' },
      );
      showSuccessToast(deleteAction ? 'Money account deleted.' : 'Money account restored.');
    } catch (cause) {
      showErrorToast(
        cause instanceof Error ? cause.message : 'Could not update money account status',
      );
      return;
    }
    try {
      await reload();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not refresh money accounts');
    }
  }

  const methodName = (id: number | null) =>
    id === null ? '—' : (methods.find((method) => method.id === id)?.name ?? '—');

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Money Accounts</h1>
          <p className="mt-1 text-sm text-slate-600">
            Track cash, bank, and mobile financial service balances for money movements.
          </p>
        </div>
        {profile?.permissions.includes('master_data.money_accounts.create') && !isFormOpen && (
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
            Add money account
          </button>
        )}
      </div>

      {isFormOpen && (
        <form
          key={selected?.id ?? 'new-money-account'}
          noValidate
          className="mt-6 grid max-w-3xl gap-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm sm:grid-cols-2"
          onSubmit={submit}
        >
          <label className="block text-sm font-medium">
            Account name<RequiredMark />
            <input
              name="name"
              placeholder="e.g. Main Bank Account"
              defaultValue={selected?.name ?? ''}
              minLength={1}
              maxLength={100}
              required
              aria-invalid={Boolean(errors.name)}
              aria-describedby={errors.name ? 'money-account-name-error' : undefined}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            />
            <FieldError id="money-account-name-error" message={errors.name} />
          </label>

          <label className="block text-sm font-medium">
            Account type<RequiredMark />
            <select
              name="type"
              defaultValue={selected?.type ?? 'CASH'}
              required
              aria-invalid={Boolean(errors.type)}
              aria-describedby={errors.type ? 'money-account-type-error' : undefined}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            >
              <option value="CASH">Cash</option>
              <option value="BANK">Bank</option>
              <option value="MFS">Mobile Financial Service</option>
            </select>
            <FieldError id="money-account-type-error" message={errors.type} />
          </label>

          <label className="block text-sm font-medium">
            Payment method
            <select
              name="payment_method_id"
              defaultValue={selected?.payment_method_id ?? ''}
              aria-invalid={Boolean(errors.payment_method_id)}
              aria-describedby={
                errors.payment_method_id ? 'money-account-method-error' : undefined
              }
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            >
              <option value="">Not linked</option>
              {methods.map((method) => (
                <option key={method.id} value={method.id}>
                  {method.name}
                </option>
              ))}
            </select>
            <FieldError id="money-account-method-error" message={errors.payment_method_id} />
          </label>

          <label className="block text-sm font-medium">
            Account number
            <input
              name="account_no"
              placeholder="Optional account or wallet number"
              defaultValue={selected?.account_no ?? ''}
              maxLength={50}
              aria-invalid={Boolean(errors.account_no)}
              aria-describedby={errors.account_no ? 'money-account-no-error' : undefined}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            />
            <FieldError id="money-account-no-error" message={errors.account_no} />
          </label>

          <label className="block text-sm font-medium">
            Opening balance<RequiredMark />
            <input
              name="opening_balance"
              type="number"
              step="0.01"
              placeholder="0.00"
              defaultValue={selected?.opening_balance ?? '0.00'}
              required
              aria-invalid={Boolean(errors.opening_balance)}
              aria-describedby={errors.opening_balance ? 'money-account-balance-error' : undefined}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            />
            <FieldError id="money-account-balance-error" message={errors.opening_balance} />
          </label>

          <div className="flex flex-col justify-center space-y-3 sm:col-span-2">
            <label className="inline-flex cursor-pointer items-center gap-2 text-sm font-medium text-slate-700">
              <input
                type="checkbox"
                name="allow_overdraft"
                defaultChecked={selected?.allow_overdraft ?? false}
                className="h-4 w-4 rounded border-slate-300 accent-emerald-700"
              />
              Allow overdraft
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
              {selected ? 'Save money account' : 'Create money account'}
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
        Show deleted money accounts
      </label>

      <div className="mt-3 overflow-x-auto rounded-lg border border-slate-200">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-4 py-3">Account</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Payment method</th>
              <th className="px-4 py-3">Account number</th>
              <th className="px-4 py-3 text-right">Opening balance</th>
              <th className="px-4 py-3">Overdraft</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {accounts.map((account) => (
              <tr key={account.id} className="hover:bg-slate-50/60">
                <td className="px-4 py-3 font-medium text-slate-900">{account.name}</td>
                <td className="px-4 py-3 text-slate-600">{typeLabels[account.type]}</td>
                <td className="px-4 py-3 text-slate-600">
                  {methodName(account.payment_method_id)}
                </td>
                <td className="px-4 py-3 font-mono text-xs text-slate-600">
                  {account.account_no ?? '—'}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-slate-800">
                  {formatAmount(account.opening_balance)}
                </td>
                <td className="px-4 py-3">
                  {account.allow_overdraft ? (
                    <span className="rounded bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-800">
                      Allowed
                    </span>
                  ) : (
                    <span className="text-slate-400">—</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  {account.deleted_at !== null ? (
                    <span className="rounded bg-rose-50 px-2 py-0.5 text-xs font-medium text-rose-700">
                      Deleted
                    </span>
                  ) : account.is_active ? (
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
                  {account.deleted_at === null &&
                    profile?.permissions.includes('master_data.money_accounts.update') && (
                      <IconActionButton
                        icon="edit"
                        label={`Edit ${account.name}`}
                        onClick={() => {
                          setErrors({});
                          setSelected(account);
                          setIsFormOpen(true);
                        }}
                        className="mr-1 p-2 text-emerald-800 hover:bg-emerald-50"
                      />
                    )}
                  {account.deleted_at === null &&
                    profile?.permissions.includes('master_data.money_accounts.delete') && (
                      <IconActionButton
                        icon="delete"
                        label={`Delete ${account.name}`}
                        onClick={() => void setDeleted(account, true)}
                        className="mr-1 p-2 text-rose-700 hover:bg-rose-50"
                      />
                    )}
                  {account.deleted_at !== null &&
                    profile?.permissions.includes('master_data.money_accounts.update') && (
                      <IconActionButton
                        icon="restore"
                        label={`Restore ${account.name}`}
                        onClick={() => void setDeleted(account, false)}
                        className="p-2 text-emerald-800 hover:bg-emerald-50"
                      />
                    )}
                </td>
              </tr>
            ))}
            {accounts.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-slate-500">
                  No money accounts found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default function MoneyAccountsPage() {
  return (
    <ProtectedPage>
      <MoneyAccountsContent />
    </ProtectedPage>
  );
}