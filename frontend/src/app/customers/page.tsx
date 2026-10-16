'use client';

import { Fragment, useEffect, useState, type FormEvent } from 'react';
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
import { PartyContacts } from '@/components/parties/party-contacts';
import { SearchableSelect } from '@/components/forms/searchable-select';
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
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [contactsCustomerId, setContactsCustomerId] = useState<number | null>(null);
  const pageSize = 25;

  async function reload() {
    const query = new URLSearchParams({
      include_inactive: String(includeInactive),
      search,
      offset: String(page * pageSize),
      limit: String(pageSize + 1),
    });
    const [customerList, listList] = await Promise.all([
      apiRequest<CustomerRecord[]>(`/api/v1/customers?${query}`),
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
  }, [includeInactive, page, search]);

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
          <p className="mt-1 text-sm text-slate-600">Manage customer master data,           Credit limit<RequiredMark />s, and opening dues.</p>
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
            <input type="text" name="code" defaultValue={selected?.code ?? ''} minLength={1} maxLength={30} required placeholder="e.g. CUS-001" className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" aria-invalid={Boolean(errors.code)} aria-describedby={errors.code ? 'customer-code-error' : undefined} />
            <FieldError id="customer-code-error" message={errors.code} />
          </label>
          <label className="block text-sm font-medium">
            Name<RequiredMark />
            <input type="text" name="name" defaultValue={selected?.name ?? ''} minLength={1} maxLength={255} required placeholder="Customer or company name" className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" aria-invalid={Boolean(errors.name)} aria-describedby={errors.name ? 'customer-name-error' : undefined} />
            <FieldError id="customer-name-error" message={errors.name} />
          </label>
          <label className="block text-sm font-medium">
            Mobile
            <input name="mobile" type="tel" inputMode="numeric" pattern="01[3-9][0-9]{8}" defaultValue={selected?.mobile ?? ''} maxLength={11} placeholder="e.g. 01712345678" className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" aria-invalid={Boolean(errors.mobile)} aria-describedby={errors.mobile ? 'customer-mobile-error' : undefined} />
            <FieldError id="customer-mobile-error" message={errors.mobile} />
          </label>
          <label className="block text-sm font-medium">
            Email
            <input name="email" type="email" defaultValue={selected?.email ?? ''} maxLength={255} placeholder="name@example.com" className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" aria-invalid={Boolean(errors.email)} aria-describedby={errors.email ? 'customer-email-error' : undefined} />
            <FieldError id="customer-email-error" message={errors.email} />
          </label>
          <label className="block text-sm font-medium sm:col-span-2">
            Address
            <textarea name="address" defaultValue={selected?.address ?? ''} rows={3} maxLength={1000} placeholder="Enter the customer's address" className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" aria-invalid={Boolean(errors.address)} aria-describedby={errors.address ? 'customer-address-error' : undefined} />
            <FieldError id="customer-address-error" message={errors.address} />
          </label>
          <label className="block text-sm font-medium">
            Price list
            <SearchableSelect
              name="price_list_id"
              aria-label="Price list"
              defaultValue={String(selected?.price_list_id ?? '')}
              placeholder="Default or search price lists"
              options={priceLists
                .filter((item) => item.deleted_at === null)
                .map((item) => ({ value: String(item.id), label: item.name }))}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            />
            <FieldError id="customer-price-list-error" message={errors.price_list_id} />
          </label>
          <label className="block text-sm font-medium">
            Credit limit<RequiredMark />
            <input name="credit_limit" type="number" step="0.01" min="0" defaultValue={selected?.credit_limit ?? '0.00'} required placeholder="0.00" className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" aria-invalid={Boolean(errors.credit_limit)} aria-describedby={errors.credit_limit ? 'customer-credit-limit-error' : undefined} />
            <FieldError id="customer-credit-limit-error" message={errors.credit_limit} />
          </label>
          <label className="block text-sm font-medium">
            Opening due<RequiredMark />
            <input name="opening_due" type="number" step="0.01" defaultValue={selected?.opening_due ?? '0.00'} required placeholder="0.00" className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" aria-invalid={Boolean(errors.opening_due)} aria-describedby={errors.opening_due ? 'customer-opening-due-error' : undefined} />
            <FieldError id="customer-opening-due-error" message={errors.opening_due} />
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
        <input type="checkbox" checked={includeInactive} onChange={(event) => { setPage(0); setIncludeInactive(event.target.checked); }} />
        Show inactive and deleted customers
      </label>
      <div className="mt-4 flex flex-wrap items-end justify-between gap-3">
        <label className="block text-sm font-medium">
          Search customers
          <input
            type="search"
            value={search}
            onChange={(event) => {
              setPage(0);
              setSearch(event.target.value);
            }}
            placeholder="Code, name, phone, or email"
            maxLength={100}
            className="mt-1 block w-72 max-w-full rounded-md border border-slate-300 px-3 py-2"
          />
        </label>
        <div className="flex items-center gap-3 text-sm">
          <button type="button" disabled={page === 0} onClick={() => setPage((value) => value - 1)} className="rounded-md border px-3 py-2 disabled:opacity-50">Previous</button>
          <span>Page {page + 1}</span>
          <button type="button" disabled={customers.length <= pageSize} onClick={() => setPage((value) => value + 1)} className="rounded-md border px-3 py-2 disabled:opacity-50">Next</button>
        </div>
      </div>

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
            {customers.slice(0, pageSize).map((customer) => (
              <Fragment key={customer.id}>
              <tr className="hover:bg-slate-50/60">
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
                  {customer.deleted_at === null && (
                    <button
                      type="button"
                      aria-expanded={contactsCustomerId === customer.id}
                      onClick={() => setContactsCustomerId((current) => current === customer.id ? null : customer.id)}
                      className="mr-1 rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50"
                    >
                      Contacts
                    </button>
                  )}
                  <a href={`/customers/${customer.id}/statement`} className="mr-1 rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50">
                    Statement
                  </a>
                  {customer.deleted_at !== null && profile?.permissions.includes('master_data.customers.update') && (
                    <IconActionButton icon="restore" label={`Restore ${customer.name}`} onClick={() => void setDeleted(customer, false)} className="p-2 text-emerald-800 hover:bg-emerald-50" />
                  )}
                </td>
              </tr>
              {contactsCustomerId === customer.id && customer.deleted_at === null && (
                <tr key={`${customer.id}-contacts`}>
                  <td colSpan={6} className="bg-slate-50 p-3">
                    <PartyContacts
                      key={customer.id}
                      partyType="customers"
                      partyId={customer.id}
                      partyName={customer.name}
                      canCreate={Boolean(profile?.permissions.includes('master_data.customers.create'))}
                      canUpdate={Boolean(profile?.permissions.includes('master_data.customers.update'))}
                      canDelete={Boolean(profile?.permissions.includes('master_data.customers.delete'))}
                    />
                  </td>
                </tr>
              )}
              </Fragment>
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
