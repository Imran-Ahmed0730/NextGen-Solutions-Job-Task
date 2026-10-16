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
import { incomeCategorySchema } from '@/lib/auth-validation';

type IncomeCategoryRecord = {
  id: number;
  name: string;
  is_active: boolean;
  deleted_at: string | null;
};

function IncomeCategoriesContent() {
  const profile = useSessionProfile();
  const [categories, setCategories] = useState<IncomeCategoryRecord[]>([]);
  const [selected, setSelected] = useState<IncomeCategoryRecord | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [includeInactive, setIncludeInactive] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});

  async function reload() {
    const query = includeInactive ? '?include_inactive=true' : '';
    setCategories(await apiRequest<IncomeCategoryRecord[]>(`/api/v1/income-categories${query}`));
  }

  useEffect(() => {
    reload().catch((cause: unknown) =>
      showErrorToast(cause instanceof Error ? cause.message : 'Could not load income categories'),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [includeInactive]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const parsed = incomeCategorySchema.safeParse({
      name: form.get('name'),
      is_active: form.get('is_active') === 'on',
    });
    if (!parsed.success) {
      setErrors(getFieldErrors(parsed.error.issues));
      return;
    }
    setErrors({});

    try {
      await apiRequest<IncomeCategoryRecord>(
        selected ? `/api/v1/income-categories/${selected.id}` : '/api/v1/income-categories',
        {
          method: selected ? 'PATCH' : 'POST',
          body: JSON.stringify(parsed.data),
        },
      );
      showSuccessToast(selected ? 'Category updated.' : 'Category created.');
      setSelected(null);
      setIsFormOpen(false);
    } catch (cause) {
      const apiErrors = getApiFieldErrors(cause);
      if (Object.keys(apiErrors).length) setErrors(apiErrors);
      else showErrorToast(cause instanceof Error ? cause.message : 'Could not save category');
      return;
    }
    try {
      await reload();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not refresh categories');
    }
  }

  async function setDeleted(category: IncomeCategoryRecord, deleteAction: boolean) {
    if (deleteAction) {
      const confirmation = await Swal.fire({
        title: 'Delete category?',
        text: `Are you sure you want to delete "${category.name}"?`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#b91c1c',
        cancelButtonColor: '#64748b',
        confirmButtonText: 'Yes, delete',
      });
      if (!confirmation.isConfirmed) return;
    }
    try {
      await apiRequest<IncomeCategoryRecord>(
        deleteAction
          ? `/api/v1/income-categories/${category.id}`
          : `/api/v1/income-categories/${category.id}/activate`,
        { method: deleteAction ? 'DELETE' : 'POST' },
      );
      showSuccessToast(deleteAction ? 'Category deleted.' : 'Category restored.');
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not update category status');
      return;
    }
    try {
      await reload();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not refresh categories');
    }
  }

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Income Categories</h1>
          <p className="mt-1 text-sm text-slate-600">
            Group income entries for cash-book and profit reporting.
          </p>
        </div>
        {profile?.permissions.includes('master_data.income_categories.create') && !isFormOpen && (
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
            Add category
          </button>
        )}
      </div>

      {isFormOpen && (
        <form
          key={selected?.id ?? 'new-income-category'}
          noValidate
          className="mt-6 grid max-w-3xl gap-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm sm:grid-cols-2"
          onSubmit={submit}
        >
          <label className="block text-sm font-medium sm:col-span-2">
            Category name<RequiredMark />
            <input type="text"
              name="name"
              placeholder="e.g. Interest Income"
              defaultValue={selected?.name ?? ''}
              minLength={1}
              maxLength={100}
              required
              aria-invalid={Boolean(errors.name)}
              aria-describedby={errors.name ? 'income-category-name-error' : undefined}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            />
            <FieldError id="income-category-name-error" message={errors.name} />
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
              {selected ? 'Save category' : 'Create category'}
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
        Show deleted categories
      </label>

      <div className="mt-3 overflow-x-auto rounded-lg border border-slate-200">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-4 py-3">Category</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {categories.map((category) => (
              <tr key={category.id} className="hover:bg-slate-50/60">
                <td className="px-4 py-3 font-medium text-slate-900">{category.name}</td>
                <td className="px-4 py-3">
                  {category.deleted_at !== null ? (
                    <span className="rounded bg-rose-50 px-2 py-0.5 text-xs font-medium text-rose-700">
                      Deleted
                    </span>
                  ) : category.is_active ? (
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
                  {category.deleted_at === null &&
                    profile?.permissions.includes('master_data.income_categories.update') && (
                      <IconActionButton
                        icon="edit"
                        label={`Edit ${category.name}`}
                        onClick={() => {
                          setErrors({});
                          setSelected(category);
                          setIsFormOpen(true);
                        }}
                        className="mr-1 p-2 text-emerald-800 hover:bg-emerald-50"
                      />
                    )}
                  {category.deleted_at === null &&
                    profile?.permissions.includes('master_data.income_categories.delete') && (
                      <IconActionButton
                        icon="delete"
                        label={`Delete ${category.name}`}
                        onClick={() => void setDeleted(category, true)}
                        className="mr-1 p-2 text-rose-700 hover:bg-rose-50"
                      />
                    )}
                  {category.deleted_at !== null &&
                    profile?.permissions.includes('master_data.income_categories.update') && (
                      <IconActionButton
                        icon="restore"
                        label={`Restore ${category.name}`}
                        onClick={() => void setDeleted(category, false)}
                        className="p-2 text-emerald-800 hover:bg-emerald-50"
                      />
                    )}
                </td>
              </tr>
            ))}
            {categories.length === 0 && (
              <tr>
                <td colSpan={3} className="px-4 py-8 text-center text-slate-500">
                  No income categories found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default function IncomeCategoriesPage() {
  return (
    <ProtectedPage>
      <IncomeCategoriesContent />
    </ProtectedPage>
  );
}