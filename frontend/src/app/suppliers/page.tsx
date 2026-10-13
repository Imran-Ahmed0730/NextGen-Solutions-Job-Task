'use client';

import { useEffect, useState, type FormEvent } from 'react';
import Swal from 'sweetalert2';

import { ProtectedPage } from '@/components/auth/protected-page';
import { useSessionProfile } from '@/components/auth/session-shell';
import { FieldError, getApiFieldErrors, getFieldErrors, RequiredMark, type FieldErrors } from '@/components/forms/field-error';
import { StatusSwitch } from '@/components/forms/status-switch';
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

  async function reload() {
    const query = includeInactive ? '?include_inactive=true' : '';
    setSuppliers(await apiRequest<SupplierRecord[]>(`/api/v1/suppliers${query}`));
  }

  useEffect(() => {
    reload().catch((cause: unknown) => showErrorToast(cause instanceof Error ? cause.message : 'Could not load suppliers'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [includeInactive]);

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
            <input name="code" defaultValue={selected?.code ?? ''} maxLength={30} required className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
            <FieldError id="field-error" message={errors.code} />
          </label>
          <label className="block text-sm font-medium">
            Name<RequiredMark />
            <input name="name" defaultValue={selected?.name ?? ''} maxLength={255} required className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
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
              {selected ? 'Save supplier' : 'Create supplier'}
            </button>
            <button type="button" onClick={() => { setSelected(null); setIsFormOpen(false); }} className="rounded-md border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50">
              Cancel
            </button>
          </div>
        </form>
      )}

      <label className="mt-6 inline-flex items-center gap-2 text-sm text-slate-600">
        <input type="checkbox" checked={includeInactive} onChange={(event) => setIncludeInactive(event.target.checked)} />
        Show deleted suppliers
      </label>

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
            {suppliers.map((supplier) => (
              <tr key={supplier.id} className="hover:bg-slate-50/60">
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
                  <a href={`/suppliers/${supplier.id}/statement`} className="mr-1 rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50">
                    Statement
                  </a>
                  {supplier.deleted_at !== null && profile?.permissions.includes('master_data.suppliers.update') && (
                    <IconActionButton icon="restore" label={`Restore ${supplier.name}`} onClick={() => void setDeleted(supplier, false)} className="p-2 text-emerald-800 hover:bg-emerald-50" />
                  )}
                </td>
              </tr>
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