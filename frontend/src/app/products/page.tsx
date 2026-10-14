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
import { SearchableSelect } from '@/components/forms/searchable-select';
import { ActionIcon, IconActionButton } from '@/components/ui/action-icon';
import { apiRequest } from '@/lib/auth-api';
import { productSchema } from '@/lib/auth-validation';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';

type ProductType = 'RAW' | 'FINISHED' | 'TRADING';

type ProductRecord = {
  id: number;
  sku: string;
  name: string;
  type: ProductType;
  category_id: number;
  category_name: string | null;
  unit_id: number;
  unit_name: string | null;
  unit_code: string | null;
  is_stocked: boolean;
  reorder_level: string;
  avg_cost: string;
  sales_price_default: string;
  description: string | null;
  is_active: boolean;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
};

type CategoryOption = { id: number; name: string; is_active: boolean; deleted_at: string | null };
type UnitOption = { id: number; name: string; code: string; is_active: boolean; deleted_at: string | null };

const productTypeLabels: Record<ProductType, { label: string; badgeClass: string }> = {
  RAW: { label: 'Raw Material', badgeClass: 'bg-amber-50 text-amber-800 border-amber-200' },
  FINISHED: { label: 'Finished Good', badgeClass: 'bg-emerald-50 text-emerald-800 border-emerald-200' },
  TRADING: { label: 'Trading', badgeClass: 'bg-blue-50 text-blue-800 border-blue-200' },
};

function ProductsContent() {
  const profile = useSessionProfile();
  const [products, setProducts] = useState<ProductRecord[]>([]);
  const [categories, setCategories] = useState<CategoryOption[]>([]);
  const [units, setUnits] = useState<UnitOption[]>([]);
  const [selected, setSelected] = useState<ProductRecord | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [includeInactive, setIncludeInactive] = useState(false);
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [errors, setErrors] = useState<FieldErrors>({});

  async function loadMetadata() {
    try {
      const [cats, u] = await Promise.all([
        apiRequest<CategoryOption[]>('/api/v1/product-categories?include_inactive=true'),
        apiRequest<UnitOption[]>('/api/v1/units?include_inactive=true'),
      ]);
      setCategories(cats);
      setUnits(u);
    } catch {
      // Optional failure - form options will reflect available items
    }
  }

  async function reload() {
    const params = new URLSearchParams();
    if (includeInactive) params.set('include_inactive', 'true');
    if (search.trim()) params.set('search', search.trim());
    if (categoryFilter) params.set('category_id', categoryFilter);
    if (typeFilter) params.set('product_type', typeFilter);

    const query = params.toString() ? `?${params.toString()}` : '';
    const data = await apiRequest<ProductRecord[]>(`/api/v1/products${query}`);
    setProducts(data);
  }

  useEffect(() => {
    void loadMetadata();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [includeInactive, search, categoryFilter, typeFilter]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);

    const parsed = productSchema.safeParse({
      sku: form.get('sku'),
      name: form.get('name'),
      type: form.get('type'),
      category_id: Number(form.get('category_id')),
      unit_id: Number(form.get('unit_id')),
      is_stocked: form.get('is_stocked') === 'on',
      reorder_level: form.get('reorder_level') || 0,
      sales_price_default: form.get('sales_price_default') || 0,
      description: form.get('description') || '',
      is_active: form.get('is_active') === 'on',
    });

    if (!parsed.success) {
      setErrors(getFieldErrors(parsed.error.issues));
      return;
    }
    setErrors({});

    try {
      await apiRequest<ProductRecord>(
        selected ? `/api/v1/products/${selected.id}` : '/api/v1/products',
        {
          method: selected ? 'PATCH' : 'POST',
          body: JSON.stringify(parsed.data),
        },
      );
      showSuccessToast(selected ? 'Product updated.' : 'Product created.');
      setSelected(null);
      setIsFormOpen(false);
    } catch (cause) {
      const apiErrors = getApiFieldErrors(cause);
      if (Object.keys(apiErrors).length) setErrors(apiErrors);
      else showErrorToast(cause instanceof Error ? cause.message : 'Could not save product');
      return;
    }

    try {
      await reload();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not refresh the product list');
    }
  }

  async function setDeleted(product: ProductRecord, deleteAction: boolean) {
    if (deleteAction) {
      const confirmation = await Swal.fire({
        title: 'Delete product?',
        text: `Are you sure you want to delete "${product.name}"? It will be archived and hidden from active lists.`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#b91c1c',
        cancelButtonColor: '#64748b',
        confirmButtonText: 'Yes, delete',
      });
      if (!confirmation.isConfirmed) return;
    }

    try {
      await apiRequest<ProductRecord>(
        deleteAction ? `/api/v1/products/${product.id}` : `/api/v1/products/${product.id}/activate`,
        { method: deleteAction ? 'DELETE' : 'POST' },
      );
      showSuccessToast(deleteAction ? 'Product deleted.' : 'Product restored.');
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not update product status');
      return;
    }

    try {
      await reload();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not refresh product list');
    }
  }

  const activeCategories = categories.filter((c) => c.is_active && c.deleted_at === null);
  const activeUnits = units.filter((u) => u.is_active && u.deleted_at === null);

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Products</h1>
          <p className="mt-1 text-sm text-slate-600">
            Manage raw materials, finished goods, trading items, units, and reorder levels.
          </p>
        </div>
        {profile?.permissions.includes('master_data.products.create') && !isFormOpen && (
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
            Add product
          </button>
        )}
      </div>

      {isFormOpen && (
        <form
          key={selected?.id ?? 'new-product'}
          noValidate
          className="mt-6 grid max-w-4xl gap-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm sm:grid-cols-2"
          onSubmit={submit}
        >
          <div className="sm:col-span-2">
            <h2 className="text-lg font-medium text-slate-900">
              {selected ? 'Edit product' : 'New product'}
            </h2>
          </div>

          <label className="block text-sm font-medium">
            SKU<RequiredMark />
            <input
              name="sku"
              placeholder="e.g. RAW-FLOUR-01"
              defaultValue={selected?.sku ?? ''}
              minLength={1}
              maxLength={50}
              required
              aria-invalid={Boolean(errors.sku)}
              aria-describedby={errors.sku ? 'product-sku-error' : undefined}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 uppercase"
            />
            <FieldError id="product-sku-error" message={errors.sku} />
          </label>

          <label className="block text-sm font-medium">
            Product name<RequiredMark />
            <input
              name="name"
              placeholder="e.g. Wheat Flour"
              defaultValue={selected?.name ?? ''}
              minLength={1}
              maxLength={255}
              required
              aria-invalid={Boolean(errors.name)}
              aria-describedby={errors.name ? 'product-name-error' : undefined}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            />
            <FieldError id="product-name-error" message={errors.name} />
          </label>

          <label className="block text-sm font-medium">
            Product type<RequiredMark />
            <select
              name="type"
              defaultValue={selected?.type ?? 'RAW'}
              required
              aria-invalid={Boolean(errors.type)}
              aria-describedby={errors.type ? 'product-type-error' : undefined}
              className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2"
            >
              <option value="RAW">Raw Material</option>
              <option value="FINISHED">Finished Good</option>
              <option value="TRADING">Trading / Resale</option>
            </select>
            <FieldError id="product-type-error" message={errors.type} />
          </label>

          <label className="block text-sm font-medium">
            Category<RequiredMark />
            <SearchableSelect
              name="category_id"
              defaultValue={String(selected?.category_id ?? '')}
              aria-label="Category"
              placeholder="Search categories"
              required
              options={activeCategories.map((category) => ({
                value: String(category.id),
                label: category.name,
                searchText: category.name,
              }))}
              aria-invalid={Boolean(errors.category_id)}
              aria-describedby={errors.category_id ? 'product-category-error' : undefined}
              className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2"
            />
            <FieldError id="product-category-error" message={errors.category_id} />
          </label>

          <label className="block text-sm font-medium">
            Unit of measure<RequiredMark />
            <SearchableSelect
              name="unit_id"
              defaultValue={String(selected?.unit_id ?? '')}
              aria-label="Unit of measure"
              placeholder="Search units"
              required
              options={activeUnits.map((unit) => ({
                value: String(unit.id),
                label: `${unit.name} (${unit.code})`,
                searchText: `${unit.name} ${unit.code}`,
              }))}
              aria-invalid={Boolean(errors.unit_id)}
              aria-describedby={errors.unit_id ? 'product-unit-error' : undefined}
              className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2"
            />
            <FieldError id="product-unit-error" message={errors.unit_id} />
          </label>

          <label className="block text-sm font-medium">
            Reorder level
            <input
              name="reorder_level"
              type="number"
              step="0.001"
              min="0"
              placeholder="0.000"
              defaultValue={selected?.reorder_level ?? '0.000'}
              aria-invalid={Boolean(errors.reorder_level)}
              aria-describedby={errors.reorder_level ? 'product-reorder-error' : undefined}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 tabular-nums"
            />
            <FieldError id="product-reorder-error" message={errors.reorder_level} />
          </label>

          <label className="block text-sm font-medium">
            Default sales price
            <input
              name="sales_price_default"
              type="number"
              step="0.01"
              min="0"
              placeholder="0.00"
              defaultValue={selected?.sales_price_default ?? '0.00'}
              aria-invalid={Boolean(errors.sales_price_default)}
              aria-describedby={errors.sales_price_default ? 'product-price-error' : undefined}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 tabular-nums"
            />
            <FieldError id="product-price-error" message={errors.sales_price_default} />
          </label>

          <div className="flex flex-col justify-center space-y-3">
            <label className="inline-flex cursor-pointer items-center gap-2 text-sm font-medium text-slate-700">
              <input
                type="checkbox"
                name="is_stocked"
                defaultChecked={selected?.is_stocked ?? true}
                className="h-4 w-4 rounded border-slate-300 accent-emerald-700"
              />
              Inventory tracked (stocked)
            </label>
            <StatusSwitch
              name="is_active"
              label="Active"
              defaultChecked={selected?.is_active ?? true}
            />
          </div>

          <label className="block text-sm font-medium sm:col-span-2">
            Description
            <textarea
              name="description"
              rows={2}
              maxLength={1000}
              placeholder="Optional notes or product specifications"
              defaultValue={selected?.description ?? ''}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            />
          </label>

          <div className="flex gap-3 sm:col-span-2">
            <button className="inline-flex items-center gap-2 rounded-md bg-emerald-700 px-4 py-2 font-medium text-white shadow-sm hover:bg-emerald-800">
              <ActionIcon name="save" />
              {selected ? 'Save product' : 'Create product'}
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

      {/* Filter and Search Bar */}
      <div className="mt-6 flex flex-wrap items-center gap-3">
        <input
          type="search"
          placeholder="Search by name or SKU..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full max-w-xs rounded-md border border-slate-300 px-3 py-1.5 text-sm"
        />
        <SearchableSelect
          aria-label="Category filter"
          value={categoryFilter}
          onChange={setCategoryFilter}
          placeholder="All categories or search"
          options={activeCategories.map((category) => ({
            value: String(category.id),
            label: category.name,
            searchText: category.name,
          }))}
          className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm"
        />
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm"
        >
          <option value="">All types</option>
          <option value="RAW">Raw Material</option>
          <option value="FINISHED">Finished Good</option>
          <option value="TRADING">Trading / Resale</option>
        </select>
        <label className="inline-flex items-center gap-2 text-sm text-slate-600">
          <input
            type="checkbox"
            checked={includeInactive}
            onChange={(e) => setIncludeInactive(e.target.checked)}
            className="rounded border-slate-300"
          />
          Show deleted products
        </label>
      </div>

      {/* Products Table */}
      <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-4 py-3">SKU</th>
              <th className="px-4 py-3">Product</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Category</th>
              <th className="px-4 py-3">Unit</th>
              <th className="px-4 py-3 text-right">Reorder level</th>
              <th className="px-4 py-3 text-right">Default price</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {products.map((product) => (
              <tr key={product.id} className="hover:bg-slate-50/60">
                <td className="px-4 py-3 font-mono text-xs font-semibold text-slate-800">
                  {product.sku}
                </td>
                <td className="px-4 py-3 font-medium text-slate-900">
                  {product.name}
                  {product.description && (
                    <p className="line-clamp-1 text-xs text-slate-500">{product.description}</p>
                  )}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-block rounded-full border px-2.5 py-0.5 text-xs font-medium ${productTypeLabels[product.type]?.badgeClass ?? 'bg-slate-100'}`}
                  >
                    {productTypeLabels[product.type]?.label ?? product.type}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-600">{product.category_name ?? '—'}</td>
                <td className="px-4 py-3 text-slate-600">
                  {product.unit_code ? `${product.unit_name} (${product.unit_code})` : '—'}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-slate-700">
                  {Number(product.reorder_level).toFixed(3)}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-slate-700">
                  {Number(product.sales_price_default).toFixed(2)}
                </td>
                <td className="px-4 py-3">
                  {product.deleted_at !== null ? (
                    <span className="rounded bg-rose-50 px-2 py-0.5 text-xs font-medium text-rose-700">
                      Deleted
                    </span>
                  ) : product.is_active ? (
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
                  {product.deleted_at === null &&
                    profile?.permissions.includes('master_data.products.update') && (
                      <IconActionButton
                        icon="edit"
                        label={`Edit ${product.name}`}
                        onClick={() => {
                          setErrors({});
                          setSelected(product);
                          setIsFormOpen(true);
                        }}
                        className="mr-1 p-2 text-emerald-800 hover:bg-emerald-50"
                      />
                    )}
                  {product.deleted_at === null &&
                    profile?.permissions.includes('master_data.products.delete') && (
                      <IconActionButton
                        icon="delete"
                        label={`Delete ${product.name}`}
                        onClick={() => void setDeleted(product, true)}
                        className="mr-1 p-2 text-rose-700 hover:bg-rose-50"
                      />
                    )}
                  {product.deleted_at !== null &&
                    profile?.permissions.includes('master_data.products.update') && (
                      <IconActionButton
                        icon="restore"
                        label={`Restore ${product.name}`}
                        onClick={() => void setDeleted(product, false)}
                        className="p-2 text-emerald-800 hover:bg-emerald-50"
                      />
                    )}
                </td>
              </tr>
            ))}
            {products.length === 0 && (
              <tr>
                <td colSpan={9} className="px-4 py-8 text-center text-slate-500">
                  No products found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default function ProductsPage() {
  return (
    <ProtectedPage>
      <ProductsContent />
    </ProtectedPage>
  );
}
