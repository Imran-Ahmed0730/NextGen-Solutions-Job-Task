'use client';

import { Fragment, useEffect, useState, type FormEvent } from 'react';
import Swal from 'sweetalert2';

import { ProtectedPage } from '@/components/auth/protected-page';
import { useSessionProfile } from '@/components/auth/session-shell';
import { FieldError, getApiFieldErrors, getFieldErrors, RequiredMark, type FieldErrors } from '@/components/forms/field-error';
import { StatusSwitch } from '@/components/forms/status-switch';
import { PartyContacts } from '@/components/parties/party-contacts';
import { ActionIcon, IconActionButton } from '@/components/ui/action-icon';
import { apiRequest } from '@/lib/auth-api';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';
import { supplierSchema } from '@/lib/auth-validation';

type SupplierRecord = {
  id: number;
  code: string;
  name: string;
  mobile: string | null;
  email: string | null;
  address: string | null;
  opening_due: string;
  is_active: boolean;
  deleted_at: string | null;
};

function SuppliersContent() {
  const profile = useSessionProfile();
  const [suppliers, setSuppliers] = useState<SupplierRecord[]>([]);
  const [selected, setSelected] = useState<SupplierRecord | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [includeInactive, setIncludeInactive] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [contactsSupplierId, setContactsSupplierId] = useState<number | null>(null);
  const pageSize = 25;

  async function reload() {
    const query = new URLSearchParams({
      include_inactive: String(includeInactive),
      search,
      offset: String(page * pageSize),
      limit: String(pageSize + 1),
    });
    setSuppliers(await apiRequest<SupplierRecord[]>(`/api/v1/suppliers?${query}`));
  }

  useEffect(() => {
    reload().catch((cause: unknown) => showErrorToast(cause instanceof Error ? cause.message : 'Could not load suppliers'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [includeInactive, page, search]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const parsed = supplierSchema.safeParse({
      code: form.get('code'),
      name: form.get('name'),
      mobile: form.get('mobile') || null,
      email: form.get('email') || null,
      address: form.get('address') || null,
      opening_due: form.get('opening_due'),
      is_active: form.get('is_active') === 'on',
    });
    if (!parsed.success) {
      setErrors(getFieldErrors(parsed.error.issues));
      return;
    }
    setErrors({});
    try {
      await apiRequest<SupplierRecord>(
        selected ? `/api/v1/suppliers/${selected.id}` : '/api/v1/suppliers',
        { method: selected ? 'PATCH' : 'POST', body: JSON.stringify(parsed.data) },
      );
      showSuccessToast(selected ? 'Supplier updated.' : 'Supplier created.');
      setSelected(null);
      setIsFormOpen(false);
      await reload();
    } catch (cause) {
      const apiErrors = getApiFieldErrors(cause);
      if (Object.keys(apiErrors).length) setErrors(apiErrors);
      else showErrorToast(cause instanceof Error ? cause.message : 'Could not save supplier');
    }
  }

  async function setDeleted(supplier: SupplierRecord, deleteAction: boolean) {
    if (deleteAction) {
      const confirmation = await Swal.fire({
        title: 'Delete supplier?',
        text: `Are you sure you want to delete "${supplier.name}"?`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#b91c1c',
        cancelButtonColor: '#64748b',
        confirmButtonText: 'Yes, delete',
      });
      if (!confirmation.isConfirmed) return;
    }
    try {
      await apiRequest<SupplierRecord>(
        deleteAction ? `/api/v1/suppliers/${supplier.id}` : `/api/v1/suppliers/${supplier.id}/activate`,
        { method: deleteAction ? 'DELETE' : 'POST' },
      );
      showSuccessToast(deleteAction ? 'Supplier deleted.' : 'Supplier restored.');
      await reload();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not update supplier status');
    }
  }

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Suppliers</h1>
          <p className="mt-1 text-sm text-slate-600">Manage supplier master data and opening dues.</p>
        </div>
        {profile?.permissions.includes('master_data.suppliers.create') && !isFormOpen && (
          <button
            type="button"
            onClick={() => { setErrors({}); setSelected(null); setIsFormOpen(true); }}
            className="inline-flex items-center gap-2 rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-emerald-800"
          >
            <ActionIcon name="add" /> Add supplier
          </button>
        )}
      </div>

      {isFormOpen && (
        <form
          key={selected?.id ?? 'new-supplier'}
          noValidate
          className="mt-6 grid max-w-3xl gap-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm sm:grid-cols-2"
          onSubmit={submit}
        >
          <label className="block text-sm font-medium">
            Code<RequiredMark />
            <input type="text" name="code" defaultValue={selected?.code ?? ''} minLength={1} maxLength={30} required placeholder="e.g. SUP-001" className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" aria-invalid={Boolean(errors.code)} aria-describedby={errors.code ? 'supplier-code-error' : undefined} />
            <FieldError id="supplier-code-error" message={errors.code} />
          </label>
          <label className="block text-sm font-medium">
            Name<RequiredMark />
            <input type="text" name="name" defaultValue={selected?.name ?? ''} minLength={1} maxLength={255} required placeholder="Supplier or company name" className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" aria-invalid={Boolean(errors.name)} aria-describedby={errors.name ? 'supplier-name-error' : undefined} />
            <FieldError id="supplier-name-error" message={errors.name} />
          </label>
          <label className="block text-sm font-medium">
            Mobile
            <input name="mobile" type="tel" inputMode="numeric" pattern="01[3-9][0-9]{8}" defaultValue={selected?.mobile ?? ''} maxLength={11} placeholder="e.g. 01712345678" className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" aria-invalid={Boolean(errors.mobile)} aria-describedby={errors.mobile ? 'supplier-mobile-error' : undefined} />
            <FieldError id="supplier-mobile-error" message={errors.mobile} />
          </label>
          <label className="block text-sm font-medium">
            Email
            <input name="email" type="email" defaultValue={selected?.email ?? ''} maxLength={255} placeholder="name@example.com" className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" aria-invalid={Boolean(errors.email)} aria-describedby={errors.email ? 'supplier-email-error' : undefined} />
            <FieldError id="supplier-email-error" message={errors.email} />
          </label>
          <label className="block text-sm font-medium sm:col-span-2">
            Address
            <textarea name="address" defaultValue={selected?.address ?? ''} rows={3} maxLength={1000} placeholder="Enter the supplier's address" className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" aria-invalid={Boolean(errors.address)} aria-describedby={errors.address ? 'supplier-address-error' : undefined} />
            <FieldError id="supplier-address-error" message={errors.address} />
          </label>
          <label className="block text-sm font-medium">
            Opening due<RequiredMark />
            <input name="opening_due" type="number" step="0.01" defaultValue={selected?.opening_due ?? '0.00'} required placeholder="0.00" className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" aria-invalid={Boolean(errors.opening_due)} aria-describedby={errors.opening_due ? 'supplier-opening-due-error' : undefined} />
            <FieldError id="supplier-opening-due-error" message={errors.opening_due} />
          </label>
          <div className="sm:col-span-2">
            <StatusSwitch name="is_active" label="Active" defaultChecked={selected?.is_active ?? true} />
          </div>
          <div className="flex gap-3 self-end sm:col-span-2">
            <button className="inline-flex items-center gap-2 rounded-md bg-emerald-700 px-4 py-2 font-medium text-white shadow-sm hover:bg-emerald-800">
              <ActionIcon name="save" />
              {selected ? 'Save supplier' : 'Create supplier'}
            </button>
            <button type="button" onClick={() => { setSelected(null); setIsFormOpen(false); }} className="rounded-md border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50">
              Cancel
            </button>
          </div>
        </form>
      )}

      <label className="mt-6 inline-flex items-center gap-2 text-sm text-slate-600">
        <input type="checkbox" checked={includeInactive} onChange={(event) => { setPage(0); setIncludeInactive(event.target.checked); }} />
        Show inactive and deleted suppliers
      </label>
      <div className="mt-4 flex flex-wrap items-end justify-between gap-3">
        <label className="block text-sm font-medium">
          Search suppliers
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
          <button type="button" disabled={suppliers.length <= pageSize} onClick={() => setPage((value) => value + 1)} className="rounded-md border px-3 py-2 disabled:opacity-50">Next</button>
        </div>
      </div>

      <div className="mt-3 overflow-x-auto rounded-lg border border-slate-200">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-4 py-3">Code</th>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3 text-right">Opening due</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {suppliers.slice(0, pageSize).map((supplier) => (
              <Fragment key={supplier.id}>
              <tr className="hover:bg-slate-50/60">
                <td className="px-4 py-3 font-medium text-slate-900">{supplier.code}</td>
                <td className="px-4 py-3 text-slate-700">{supplier.name}</td>
                <td className="px-4 py-3 text-right tabular-nums text-slate-800">{Number(supplier.opening_due).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                <td className="px-4 py-3">
                  {supplier.deleted_at !== null ? <span className="rounded bg-rose-50 px-2 py-0.5 text-xs font-medium text-rose-700">Deleted</span> : supplier.is_active ? <span className="rounded bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-800">Active</span> : <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">Inactive</span>}
                </td>
                <td className="px-4 py-3">
                  {supplier.deleted_at === null && profile?.permissions.includes('master_data.suppliers.update') && (
                    <IconActionButton icon="edit" label={`Edit ${supplier.name}`} onClick={() => { setErrors({}); setSelected(supplier); setIsFormOpen(true); }} className="mr-1 p-2 text-emerald-800 hover:bg-emerald-50" />
                  )}
                  {supplier.deleted_at === null && profile?.permissions.includes('master_data.suppliers.delete') && (
                    <IconActionButton icon="delete" label={`Delete ${supplier.name}`} onClick={() => void setDeleted(supplier, true)} className="mr-1 p-2 text-rose-700 hover:bg-rose-50" />
                  )}
                  {supplier.deleted_at === null && (
                    <button
                      type="button"
                      aria-expanded={contactsSupplierId === supplier.id}
                      onClick={() => setContactsSupplierId((current) => current === supplier.id ? null : supplier.id)}
                      className="mr-1 rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50"
                    >
                      Contacts
                    </button>
                  )}
                  <a href={`/suppliers/${supplier.id}/statement`} className="mr-1 rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50">
                    Statement
                  </a>
                  {supplier.deleted_at !== null && profile?.permissions.includes('master_data.suppliers.update') && (
                    <IconActionButton icon="restore" label={`Restore ${supplier.name}`} onClick={() => void setDeleted(supplier, false)} className="p-2 text-emerald-800 hover:bg-emerald-50" />
                  )}
                </td>
              </tr>
              {contactsSupplierId === supplier.id && supplier.deleted_at === null && (
                <tr>
                  <td colSpan={5} className="bg-slate-50 p-3">
                    <PartyContacts
                      key={supplier.id}
                      partyType="suppliers"
                      partyId={supplier.id}
                      partyName={supplier.name}
                      canCreate={Boolean(profile?.permissions.includes('master_data.suppliers.create'))}
                      canUpdate={Boolean(profile?.permissions.includes('master_data.suppliers.update'))}
                      canDelete={Boolean(profile?.permissions.includes('master_data.suppliers.delete'))}
                    />
                  </td>
                </tr>
              )}
              </Fragment>
            ))}
            {suppliers.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-500">No suppliers found.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default function SuppliersPage() {
  return (
    <ProtectedPage>
      <SuppliersContent />
    </ProtectedPage>
  );
}