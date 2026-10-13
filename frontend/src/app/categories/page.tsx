'use client';

import { useEffect, useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { useSessionProfile } from '@/components/auth/session-shell';
import {
  FieldError,
  getFieldErrors,
  RequiredMark,
  type FieldErrors,
} from '@/components/forms/field-error';
import { apiRequest } from '@/lib/auth-api';
import { productCategorySchema } from '@/lib/auth-validation';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';

type CategoryRecord = {
  id: number;
  name: string;
  parent_id: number | null;
  is_active: boolean;
  deleted_at: string | null;
};

function categoryDepth(category: CategoryRecord, categories: CategoryRecord[]): number {
  const byId = new Map(categories.map((item) => [item.id, item]));
  const visited = new Set<number>([category.id]);
  let depth = 0;
  let parentId = category.parent_id;
  while (parentId !== null && !visited.has(parentId)) {
    visited.add(parentId);
    const parent = byId.get(parentId);
    if (!parent) break;
    depth += 1;
    parentId = parent.parent_id;
  }
  return depth;
}

function isDescendant(
  possibleDescendantId: number,
  categoryId: number,
  categories: CategoryRecord[],
): boolean {
  const byId = new Map(categories.map((item) => [item.id, item]));
  let parentId = byId.get(possibleDescendantId)?.parent_id ?? null;
  const visited = new Set<number>();
  while (parentId !== null && !visited.has(parentId)) {
    if (parentId === categoryId) return true;
    visited.add(parentId);
    parentId = byId.get(parentId)?.parent_id ?? null;
  }
  return false;
}

function CategoriesContent() {
  const profile = useSessionProfile();
  const [categories, setCategories] = useState<CategoryRecord[]>([]);
  const [selected, setSelected] = useState<CategoryRecord | null>(null);
  const [includeInactive, setIncludeInactive] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});

  useEffect(() => {
    apiRequest<CategoryRecord[]>('/api/v1/product-categories?include_inactive=true')
      .then(setCategories)
      .catch((cause: unknown) =>
        showErrorToast(cause instanceof Error ? cause.message : 'Could not load categories'),
      );
  }, []);

  async function reload() {
    setCategories(
      await apiRequest<CategoryRecord[]>('/api/v1/product-categories?include_inactive=true'),
    );
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const parentValue = form.get('parent_id');
    const parsed = productCategorySchema.safeParse({
      name: form.get('name'),
      parent_id: typeof parentValue === 'string' && parentValue ? Number(parentValue) : null,
    });
    if (!parsed.success) {
      setErrors(getFieldErrors(parsed.error.issues));
      return;
    }
    setErrors({});

    try {
      await apiRequest<CategoryRecord>(
        selected ? `/api/v1/product-categories/${selected.id}` : '/api/v1/product-categories',
        {
          method: selected ? 'PATCH' : 'POST',
          body: JSON.stringify(parsed.data),
        },
      );
      showSuccessToast(selected ? 'Category updated.' : 'Category created.');
      setSelected(null);
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not save category');
      return;
    }
    try {
      await reload();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not refresh categories');
    }
  }

  async function setActive(category: CategoryRecord, active: boolean) {
    try {
      await apiRequest<CategoryRecord>(
        active
          ? `/api/v1/product-categories/${category.id}/activate`
          : `/api/v1/product-categories/${category.id}`,
        { method: active ? 'POST' : 'DELETE' },
      );
      showSuccessToast(active ? 'Category restored.' : 'Category deleted.');
      if (selected?.id === category.id) setSelected(null);
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not update category');
      return;
    }
    try {
      await reload();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not refresh categories');
    }
  }

  const visibleCategories = categories.filter(
    (category) => includeInactive || (category.is_active && category.deleted_at === null),
  );
  const possibleParents = categories.filter(
    (category) =>
      category.is_active &&
      category.deleted_at === null &&
      (!selected ||
        (category.id !== selected.id &&
          !isDescendant(category.id, selected.id, categories))),
  );
  const selectedParent =
    selected?.parent_id === null || selected?.parent_id === undefined
      ? undefined
      : categories.find((category) => category.id === selected.parent_id);

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Product Categories</h1>
          <p className="mt-1 text-sm text-slate-600">
            Organize products into parent and child categories.
          </p>
        </div>
        {profile?.permissions.includes('master_data.product_categories.create') && (
          <button
            type="button"
            onClick={() => {
              setErrors({});
              setSelected(null);
            }}
            className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white"
          >
            Add category
          </button>
        )}
      </div>

      {(selected
        ? profile?.permissions.includes('master_data.product_categories.update')
        : profile?.permissions.includes('master_data.product_categories.create')) && (
        <form
          key={selected?.id ?? 'new-category'}
          noValidate
          className="mt-6 grid max-w-3xl gap-4 rounded-lg border border-slate-200 p-4 sm:grid-cols-2"
          onSubmit={submit}
        >
          <label className="block text-sm font-medium">
            Category name<RequiredMark />
            <input
              name="name"
              placeholder="e.g. Raw Materials"
              defaultValue={selected?.name ?? ''}
              required
              aria-invalid={Boolean(errors.name)}
              aria-describedby={errors.name ? 'category-name-error' : undefined}
              className="mt-1 w-full rounded-md border px-3 py-2"
            />
            <FieldError id="category-name-error" message={errors.name} />
          </label>
          <label className="block text-sm font-medium">
            Parent category
            <select
              name="parent_id"
              defaultValue={selected?.parent_id ?? ''}
              aria-invalid={Boolean(errors.parent_id)}
              aria-describedby={errors.parent_id ? 'category-parent-error' : undefined}
              className="mt-1 w-full rounded-md border bg-white px-3 py-2"
            >
              <option value="">No parent (top-level)</option>
              {selectedParent &&
                (!selectedParent.is_active || selectedParent.deleted_at !== null) &&
                !possibleParents.some((category) => category.id === selectedParent.id) && (
                  <option value={selectedParent.id}>
                    {selectedParent.name} (inactive parent)
                  </option>
                )}
              {possibleParents.map((category) => (
                <option key={category.id} value={category.id}>
                  {'— '.repeat(categoryDepth(category, categories))}
                  {category.name}
                </option>
              ))}
            </select>
            <FieldError id="category-parent-error" message={errors.parent_id} />
          </label>
          <div className="flex gap-3 sm:col-span-2">
            <button className="rounded-md bg-emerald-700 px-4 py-2 font-medium text-white">
              {selected ? 'Save category' : 'Create category'}
            </button>
            {selected && (
              <button
                type="button"
                onClick={() => setSelected(null)}
                className="rounded-md border border-slate-300 px-4 py-2"
              >
                Cancel
              </button>
            )}
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
              <th className="px-4 py-3">Parent category</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {visibleCategories.map((category) => {
              const parent = categories.find((item) => item.id === category.parent_id);
              return (
                <tr key={category.id}>
                  <td className="px-4 py-3 font-medium">
                    {'— '.repeat(categoryDepth(category, categories))}
                    {category.name}
                  </td>
                  <td className="px-4 py-3">{parent?.name ?? '—'}</td>
                  <td className="px-4 py-3">{category.is_active ? 'Active' : 'Deleted'}</td>
                  <td className="space-x-3 px-4 py-3">
                    {category.is_active &&
                      profile?.permissions.includes('master_data.product_categories.update') && (
                        <button
                          type="button"
                          onClick={() => {
                            setErrors({});
                            setSelected(category);
                          }}
                          className="text-emerald-800 underline"
                        >
                          Edit
                        </button>
                      )}
                    {category.is_active &&
                      profile?.permissions.includes('master_data.product_categories.delete') && (
                        <button
                          type="button"
                          onClick={() => void setActive(category, false)}
                          className="text-rose-700 underline"
                        >
                          Delete
                        </button>
                      )}
                    {!category.is_active &&
                      profile?.permissions.includes('master_data.product_categories.update') && (
                        <button
                          type="button"
                          onClick={() => void setActive(category, true)}
                          className="text-emerald-800 underline"
                        >
                          Restore
                        </button>
                      )}
                  </td>
                </tr>
              );
            })}
            {visibleCategories.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-slate-500">
                  No product categories found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default function CategoriesPage() {
  return (
    <ProtectedPage>
      <CategoriesContent />
    </ProtectedPage>
  );
}
