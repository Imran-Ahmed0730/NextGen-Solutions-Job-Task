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
import { customerSchema } from '@/lib/auth-validation';

type PriceListRecord = { id: number; name: string; is_default: boolean; deleted_at: string | null };
type CustomerRecord = {
  id: number;
  code: string;
  name: string;
  mobile: string | null;
  email: string | null;
  address: string | null;
  credit_limit: string;
  opening_due: string;
  price_list_id: number | null;
  is_active: boolean;
  deleted_at: string | null;
};

function CustomersContent() {
  const profile = useSessionProfile();
  const [customers, setCustomers] = useState<CustomerRecord[]>([]);
  const [priceLists, setPriceLists] = useState<PriceListRecord[]>([]);
  const [selected, setSelected] = useState<CustomerRecord | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [includeInactive, setIncludeInactive] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});

  async function reload() {
    const query = includeInactive ? '?include_inactive=true' : '';
    const [customerList, listList] = await Promise.all([
      apiRequest<CustomerRecord[]>(`/api/v1/customers${query}`),
      apiRequest<PriceListRecord[]>('/api/v1/price-lists?include_inactive=true'),
    ]);
    setCustomers(customerList);
    setPriceLists(listList);
  }

  useEffect(() => {
    reload().catch((cause: unknown) =>
      showErrorToast(cause instanceof Error ? cause.message : 'Could not load customers'),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [includeInactive]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const rawPriceList = form.get('price_list_id');
    const parsed = customerSchema.safeParse({
      code: form.get('code'),
      name: form.get('name'),
      mobile: form.get('mobile') || null,
      email: form.get('email') || null,
      address: form.get('address') || null,
      credit_limit: form.get('credit_limit'),
      opening_due: form.get('opening_due'),
      price_list_id: rawPriceList ? Number(rawPriceList) : null,
      is_active: form.get('is_active') === 'on',
    });
    if (!parsed.success) {
      setErrors(getFieldErrors(parsed.error.issues));
      return;
    }
    setErrors({});
    try {
      await apiRequest<CustomerRecord>(
        selected ? `/api/v1/customers/${selected.id}` : '/api/v1/customers',
        { method: selected ? 'PATCH' : 'POST', body: JSON.stringify(parsed.data) },
      );
      showSuccessToast(selected ? 'Customer updated.' : 'Customer created.');
      setSelected(null);
      setIsFormOpen(false);
      await reload();
    } catch (cause) {
      const apiErrors = getApiFieldErrors(cause);
      if (Object.keys(apiErrors).length) setErrors(apiErrors);
      else showErrorToast(cause instanceof Error ? cause.message : 'Could not save customer');
    }
  }

  async function setDeleted(customer: CustomerRecord, deleteAction: boolean) {
    if (deleteAction) {
      const confirmation = await Swal.fire({
        title: 'Delete customer?',
        text: `Are you sure you want to delete "${customer.name}"?`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#b91c1c',
        cancelButtonColor: '#64748b',
        confirmButtonText: 'Yes, delete',
      });
      if (!confirmation.isConfirmed) return;
    }
    try {
      await apiRequest<CustomerRecord>(
        deleteAction ? `/api/v1/customers/${customer.id}` : `/api/v1/customers/${customer.id}/activate`,
        { method: deleteAction ? 'DELETE' : 'POST' },
      );
      showSuccessToast(deleteAction ? 'Customer deleted.' : 'Customer restored.');
      await reload();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not update customer status');
    }
  }

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Customers</h1>
          <p className="mt-1 text-sm text-slate-600">Manage customer master data, credit limits, and opening dues.</p>
        </div>
        {profile?.permissions.includes('master_data.customers.create') && !isFormOpen && (
          <button
            type="button"
            onClick={() => { setErrors({}); setSelected(null); setIsFormOpen(true); }}
            className="inline-flex items-center gap-2 rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-emerald-800"
          >
            <ActionIcon name="add" /> Add customer
          </button>
        )}
      </div>

      {isFormOpen && (
        <form
          key={selected?.id ?? 'new-customer'}
          noValidate
          className="mt-6 grid max-w-4xl gap-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm sm:grid-cols-2"
          onSubmit={submit}
        >
          <label className="block text-sm font-medium">
            Code<RequiredMark />
            <input name="code" defaultValue={selected?.code ?? ''} maxLength={30} required className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" aria-invalid={Boolean(errors.code)} />
            <FieldError id="field-error" message={errors.code} />
          </label>
          <label className="block text-sm font-medium">
            Name<RequiredMark />
            <input name="name" defaultValue={selected?.name ?? ''} maxLength={255} required className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" aria-invalid={Boolean(errors.name)} />
            <FieldError id="field-error" message={errors.name} />
          </label>
          <label className="block text-sm font-medium">
            Mobile
            <input name="mobile" defaultValue={selected?.mobile ?? ''} maxLength={30} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
            <FieldError id="field-error" message={errors.mobile} />
          </label>
          <label className="block text-sm font-medium">
            Email
            <input name="email" defaultValue={selected?.email ?? ''} maxLength={255} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
            <FieldError id="field-error" message={errors.email} />
          </label>
          <label className="block text-sm font-medium sm:col-span-2">
            Address
            <textarea name="address" defaultValue={selected?.address ?? ''} rows={3} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
            <FieldError id="field-error" message={errors.address} />
          </label>
          <label className="block text-sm font-medium">
            Price list
            <select name="price_list_id" defaultValue={selected?.price_list_id ?? ''} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2">
              <option value="">Default</option>
              {priceLists.filter((item) => item.deleted_at === null).map((item) => (
                <option key={item.id} value={item.id}>{item.name}</option>
              ))}
            </select>
            <FieldError id="field-error" message={errors.price_list_id} />
          </label>
          <label className="block text-sm font-medium">
            Credit limit
            <input name="credit_limit" type="number" step="0.01" min="0" defaultValue={selected?.credit_limit ?? '0.00'} required className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
            <FieldError id="field-error" message={errors.credit_limit} />
          </label>
          <label className="block text-sm font-medium">
            Opening due
            <input name="opening_due" type="number" step="0.01" defaultValue={selected?.opening_due ?? '0.00'} required className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
            <FieldError id="field-error" message={errors.opening_due} />
          </label>
          <div className="sm:col-span-2">
            <StatusSwitch name="is_active" label="Active" defaultChecked={selected?.is_active ?? true} />
          </div>
          <div className="flex gap-3 self-end sm:col-span-2">
            <button className="inline-flex items-center gap-2 rounded-md bg-emerald-700 px-4 py-2 font-medium text-white shadow-sm hover:bg-emerald-800">
              <ActionIcon name="save" />
              {selected ? 'Save customer' : 'Create customer'}
            </button>
            <button type="button" onClick={() => { setSelected(null); setIsFormOpen(false); }} className="rounded-md border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50">
              Cancel
            </button>
          </div>
        </form>
      )}

      <label className="mt-6 inline-flex items-center gap-2 text-sm text-slate-600">
        <input type="checkbox" checked={includeInactive} onChange={(event) => setIncludeInactive(event.target.checked)} />
        Show deleted customers
      </label>

      <div className="mt-3 overflow-x-auto rounded-lg border border-slate-200">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-4 py-3">Code</th>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Credit limit</th>
              <th className="px-4 py-3">Opening due</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {customers.map((customer) => (
              <tr key={customer.id} className="hover:bg-slate-50/60">
                <td className="px-4 py-3 font-medium text-slate-900">{customer.code}</td>
                <td className="px-4 py-3 text-slate-700">{customer.name}</td>
                <td className="px-4 py-3 text-right tabular-nums text-slate-800">{Number(customer.credit_limit).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                <td className="px-4 py-3 text-right tabular-nums text-slate-800">{Number(customer.opening_due).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                <td className="px-4 py-3">
                  {customer.deleted_at !== null ? <span className="rounded bg-rose-50 px-2 py-0.5 text-xs font-medium text-rose-700">Deleted</span> : customer.is_active ? <span className="rounded bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-800">Active</span> : <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">Inactive</span>}
                </td>
                <td className="px-4 py-3">
                  {customer.deleted_at === null && profile?.permissions.includes('master_data.customers.update') && (
                    <IconActionButton icon="edit" label={`Edit ${customer.name}`} onClick={() => { setErrors({}); setSelected(customer); setIsFormOpen(true); }} className="mr-1 p-2 text-emerald-800 hover:bg-emerald-50" />
                  )}
                  {customer.deleted_at === null && profile?.permissions.includes('master_data.customers.delete') && (
                    <IconActionButton icon="delete" label={`Delete ${customer.name}`} onClick={() => void setDeleted(customer, true)} className="mr-1 p-2 text-rose-700 hover:bg-rose-50" />
                  )}
                  <a href={`/customers/${customer.id}/statement`} className="mr-1 rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50">
                    Statement
                  </a>
                  {customer.deleted_at !== null && profile?.permissions.includes('master_data.customers.update') && (
                    <IconActionButton icon="restore" label={`Restore ${customer.name}`} onClick={() => void setDeleted(customer, false)} className="p-2 text-emerald-800 hover:bg-emerald-50" />
                  )}
                </td>
              </tr>
            ))}
            {customers.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-500">No customers found.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default function CustomersPage() {
  return (
    <ProtectedPage>
      <CustomersContent />
    </ProtectedPage>
  );
}
