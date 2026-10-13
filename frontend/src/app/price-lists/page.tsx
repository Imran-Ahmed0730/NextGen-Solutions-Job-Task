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
import { priceListSchema, productPriceSchema } from '@/lib/auth-validation';

type PriceListRecord = {
  id: number;
  name: string;
  is_default: boolean;
  valid_from: string | null;
  valid_to: string | null;
  is_active: boolean;
  deleted_at: string | null;
};

type ProductRecord = {
  id: number;
  name: string;
  sku: string;
  is_active: boolean;
  deleted_at: string | null;
};

type ProductPriceRecord = {
  id: number;
  price_list_id: number;
  product_id: number;
  price: string | number;
  created_at: string;
  updated_at: string;
};

function PriceListsContent() {
  const profile = useSessionProfile();
  const [priceLists, setPriceLists] = useState<PriceListRecord[]>([]);
  const [products, setProducts] = useState<ProductRecord[]>([]);
  const [selected, setSelected] = useState<PriceListRecord | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [includeInactive, setIncludeInactive] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [managedList, setManagedList] = useState<PriceListRecord | null>(null);
  const [prices, setPrices] = useState<ProductPriceRecord[]>([]);
  const [priceSelected, setPriceSelected] = useState<ProductPriceRecord | null>(null);
  const [isPriceFormOpen, setIsPriceFormOpen] = useState(false);
  const [priceErrors, setPriceErrors] = useState<FieldErrors>({});

  async function reload() {
    const query = includeInactive ? '?include_inactive=true' : '';
    const [list, productList] = await Promise.all([
      apiRequest<PriceListRecord[]>(`/api/v1/price-lists${query}`),
      apiRequest<ProductRecord[]>('/api/v1/products?include_inactive=true'),
    ]);
    setPriceLists(list);
    setProducts(productList);
  }

  async function reloadPrices(priceListId: number) {
    const result = await apiRequest<ProductPriceRecord[]>(
      `/api/v1/price-lists/${priceListId}/prices`,
    );
    setPrices(result);
  }

  useEffect(() => {
    reload().catch((cause: unknown) =>
      showErrorToast(cause instanceof Error ? cause.message : 'Could not load price lists'),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [includeInactive]);

  useEffect(() => {
    if (managedList !== null) {
      reloadPrices(managedList.id).catch((cause: unknown) =>
        showErrorToast(cause instanceof Error ? cause.message : 'Could not load product prices'),
      );
    }
  }, [managedList]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const rawValidFrom = form.get('valid_from');
    const rawValidTo = form.get('valid_to');
    const parsed = priceListSchema.safeParse({
      name: form.get('name'),
      is_default: form.get('is_default') === 'on',
      valid_from: rawValidFrom === '' || rawValidFrom === null ? null : String(rawValidFrom),
      valid_to: rawValidTo === '' || rawValidTo === null ? null : String(rawValidTo),
      is_active: form.get('is_active') === 'on',
    });
    if (!parsed.success) {
      setErrors(getFieldErrors(parsed.error.issues));
      return;
    }
    setErrors({});

    try {
      await apiRequest<PriceListRecord>(
        selected ? `/api/v1/price-lists/${selected.id}` : '/api/v1/price-lists',
        {
          method: selected ? 'PATCH' : 'POST',
          body: JSON.stringify(parsed.data),
        },
      );
      showSuccessToast(selected ? 'Price list updated.' : 'Price list created.');
      setSelected(null);
      setIsFormOpen(false);
    } catch (cause) {
      const apiErrors = getApiFieldErrors(cause);
      if (Object.keys(apiErrors).length) setErrors(apiErrors);
      else showErrorToast(cause instanceof Error ? cause.message : 'Could not save price list');
      return;
    }
    try {
      await reload();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not refresh price lists');
    }
  }

  async function setDeleted(priceList: PriceListRecord, deleteAction: boolean) {
    if (deleteAction) {
      const confirmation = await Swal.fire({
        title: 'Delete price list?',
        text: `Are you sure you want to delete "${priceList.name}"?`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#b91c1c',
        cancelButtonColor: '#64748b',
        confirmButtonText: 'Yes, delete',
      });
      if (!confirmation.isConfirmed) return;
    }
    try {
      await apiRequest<PriceListRecord>(
        deleteAction
          ? `/api/v1/price-lists/${priceList.id}`
          : `/api/v1/price-lists/${priceList.id}/activate`,
        { method: deleteAction ? 'DELETE' : 'POST' },
      );
      showSuccessToast(deleteAction ? 'Price list deleted.' : 'Price list restored.');
      if (managedList?.id === priceList.id && deleteAction) {
        setManagedList(null);
        setPrices([]);
      }
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not update price list status');
      return;
    }
    try {
      await reload();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not refresh price lists');
    }
  }

  async function submitPrice(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (managedList === null) return;
    const form = new FormData(event.currentTarget);
    const parsed = productPriceSchema.safeParse({
      product_id: Number(form.get('product_id')),
      price: form.get('price'),
    });
    if (!parsed.success) {
      setPriceErrors(getFieldErrors(parsed.error.issues));
      return;
    }
    setPriceErrors({});

    try {
      await apiRequest<ProductPriceRecord>(
        priceSelected
          ? `/api/v1/price-lists/${managedList.id}/prices/${priceSelected.id}`
          : `/api/v1/price-lists/${managedList.id}/prices`,
        {
          method: priceSelected ? 'PATCH' : 'POST',
          body: JSON.stringify(parsed.data),
        },
      );
      showSuccessToast(priceSelected ? 'Price updated.' : 'Price added.');
      setPriceSelected(null);
      setIsPriceFormOpen(false);
    } catch (cause) {
      const apiErrors = getApiFieldErrors(cause);
      if (Object.keys(apiErrors).length) setPriceErrors(apiErrors);
      else showErrorToast(cause instanceof Error ? cause.message : 'Could not save price');
      return;
    }
    try {
      await reloadPrices(managedList.id);
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not refresh prices');
    }
  }

  async function deletePrice(price: ProductPriceRecord) {
    if (managedList === null) return;
    const confirmation = await Swal.fire({
      title: 'Delete price?',
      text: 'This removes the product price from the price list.',
      icon: 'warning',
      showCancelButton: true,
      confirmButtonColor: '#b91c1c',
      cancelButtonColor: '#64748b',
      confirmButtonText: 'Yes, delete',
    });
    if (!confirmation.isConfirmed) return;
    try {
      await apiRequest<void>(
        `/api/v1/price-lists/${managedList.id}/prices/${price.id}`,
        { method: 'DELETE' },
      );
      showSuccessToast('Price deleted.');
      await reloadPrices(managedList.id);
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not delete price');
    }
  }

  const productName = (id: number) =>
    products.find((product) => product.id === id)?.name ?? `Product ${id}`;

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Price Lists</h1>
          <p className="mt-1 text-sm text-slate-600">
            Maintain named price lists and the prices applied to products.
          </p>
        </div>
        {profile?.permissions.includes('master_data.price_lists.create') && !isFormOpen && (
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
            Add price list
          </button>
        )}
      </div>

      {isFormOpen && (
        <form
          key={selected?.id ?? 'new-price-list'}
          noValidate
          className="mt-6 grid max-w-3xl gap-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm sm:grid-cols-2"
          onSubmit={submit}
        >
          <label className="block text-sm font-medium sm:col-span-2">
            Price list name<RequiredMark />
            <input
              name="name"
              placeholder="e.g. Retail Price List"
              defaultValue={selected?.name ?? ''}
              minLength={1}
              maxLength={100}
              required
              aria-invalid={Boolean(errors.name)}
              aria-describedby={errors.name ? 'price-list-name-error' : undefined}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            />
            <FieldError id="price-list-name-error" message={errors.name} />
          </label>

          <label className="block text-sm font-medium">
            Valid from
            <input
              name="valid_from"
              type="date"
              defaultValue={selected?.valid_from ?? ''}
              aria-invalid={Boolean(errors.valid_from)}
              aria-describedby={errors.valid_from ? 'price-list-from-error' : undefined}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            />
            <FieldError id="price-list-from-error" message={errors.valid_from} />
          </label>

          <label className="block text-sm font-medium">
            Valid to
            <input
              name="valid_to"
              type="date"
              defaultValue={selected?.valid_to ?? ''}
              aria-invalid={Boolean(errors.valid_to)}
              aria-describedby={errors.valid_to ? 'price-list-to-error' : undefined}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            />
            <FieldError id="price-list-to-error" message={errors.valid_to} />
          </label>

          <div className="flex flex-col justify-center space-y-3 sm:col-span-2">
            <label className="inline-flex cursor-pointer items-center gap-2 text-sm font-medium text-slate-700">
              <input
                type="checkbox"
                name="is_default"
                defaultChecked={selected?.is_default ?? false}
                className="h-4 w-4 rounded border-slate-300 accent-emerald-700"
              />
              Default price list
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
              {selected ? 'Save price list' : 'Create price list'}
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
        Show deleted price lists
      </label>

      <div className="mt-3 overflow-x-auto rounded-lg border border-slate-200">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-4 py-3">Price list</th>
              <th className="px-4 py-3">Default</th>
              <th className="px-4 py-3">Valid from</th>
              <th className="px-4 py-3">Valid to</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {priceLists.map((priceList) => (
              <tr key={priceList.id} className="hover:bg-slate-50/60">
                <td className="px-4 py-3 font-medium text-slate-900">{priceList.name}</td>
                <td className="px-4 py-3">
                  {priceList.is_default ? (
                    <span className="rounded bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-800">
                      Default
                    </span>
                  ) : (
                    <span className="text-slate-400">—</span>
                  )}
                </td>
                <td className="px-4 py-3 text-slate-600">{priceList.valid_from ?? '—'}</td>
                <td className="px-4 py-3 text-slate-600">{priceList.valid_to ?? '—'}</td>
                <td className="px-4 py-3">
                  {priceList.deleted_at !== null ? (
                    <span className="rounded bg-rose-50 px-2 py-0.5 text-xs font-medium text-rose-700">
                      Deleted
                    </span>
                  ) : priceList.is_active ? (
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
                  {priceList.deleted_at === null &&
                    profile?.permissions.includes('master_data.price_lists.update') && (
                      <IconActionButton
                        icon="edit"
                        label={`Edit ${priceList.name}`}
                        onClick={() => {
                          setErrors({});
                          setSelected(priceList);
                          setIsFormOpen(true);
                        }}
                        className="mr-1 p-2 text-emerald-800 hover:bg-emerald-50"
                      />
                    )}
                  {profile?.permissions.includes('master_data.price_lists.read') && (
                    <button
                      type="button"
                      onClick={() => setManagedList(priceList)}
                      className="mr-1 rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50"
                    >
                      Prices
                    </button>
                  )}
                  {priceList.deleted_at === null &&
                    profile?.permissions.includes('master_data.price_lists.delete') && (
                      <IconActionButton
                        icon="delete"
                        label={`Delete ${priceList.name}`}
                        onClick={() => void setDeleted(priceList, true)}
                        className="mr-1 p-2 text-rose-700 hover:bg-rose-50"
                      />
                    )}
                  {priceList.deleted_at !== null &&
                    profile?.permissions.includes('master_data.price_lists.update') && (
                      <IconActionButton
                        icon="restore"
                        label={`Restore ${priceList.name}`}
                        onClick={() => void setDeleted(priceList, false)}
                        className="p-2 text-emerald-800 hover:bg-emerald-50"
                      />
                    )}
                </td>
              </tr>
            ))}
            {priceLists.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                  No price lists found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {managedList !== null && (
        <div className="mt-8 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-semibold">Prices for {managedList.name}</h2>
            {profile?.permissions.includes('master_data.price_lists.create') && !isPriceFormOpen && (
              <button
                type="button"
                onClick={() => {
                  setPriceErrors({});
                  setPriceSelected(null);
                  setIsPriceFormOpen(true);
                }}
                className="inline-flex items-center gap-2 rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-emerald-800"
              >
                <ActionIcon name="add" />
                Add price
              </button>
            )}
          </div>

          {isPriceFormOpen && (
            <form
              key={priceSelected?.id ?? 'new-price'}
              noValidate
              className="mt-4 grid max-w-3xl gap-4 rounded-xl border border-slate-200 bg-slate-50 p-4 sm:grid-cols-2"
              onSubmit={submitPrice}
            >
              <label className="block text-sm font-medium">
                Product<RequiredMark />
                <select
                  name="product_id"
                  defaultValue={priceSelected?.product_id ?? ''}
                  required
                  aria-invalid={Boolean(priceErrors.product_id)}
                  aria-describedby={priceErrors.product_id ? 'price-product-error' : undefined}
                  className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2"
                >
                  <option value="">Select a product</option>
                  {products
                    .filter((product) => product.deleted_at === null)
                    .map((product) => (
                      <option key={product.id} value={product.id}>
                        {product.name} ({product.sku})
                      </option>
                    ))}
                </select>
                <FieldError id="price-product-error" message={priceErrors.product_id} />
              </label>

              <label className="block text-sm font-medium">
                Price<RequiredMark />
                <input
                  name="price"
                  type="number"
                  step="0.01"
                  min="0"
                  placeholder="0.00"
                  defaultValue={priceSelected?.price ?? ''}
                  required
                  aria-invalid={Boolean(priceErrors.price)}
                  aria-describedby={priceErrors.price ? 'price-value-error' : undefined}
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
                />
                <FieldError id="price-value-error" message={priceErrors.price} />
              </label>

              <div className="flex gap-3 self-end sm:col-span-2">
                <button className="inline-flex items-center gap-2 rounded-md bg-emerald-700 px-4 py-2 font-medium text-white shadow-sm hover:bg-emerald-800">
                  <ActionIcon name="save" />
                  {priceSelected ? 'Save price' : 'Add price'}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setPriceSelected(null);
                    setIsPriceFormOpen(false);
                  }}
                  className="rounded-md border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
              </div>
            </form>
          )}

          <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="px-4 py-3">Product</th>
                  <th className="px-4 py-3 text-right">Price</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {prices.map((price) => (
                  <tr key={price.id} className="hover:bg-slate-50/60">
                    <td className="px-4 py-3 font-medium text-slate-900">
                      {productName(price.product_id)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-slate-800">
                      {Number(price.price).toLocaleString('en-US', {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}
                    </td>
                    <td className="px-4 py-3">
                      {profile?.permissions.includes('master_data.price_lists.update') && (
                        <IconActionButton
                          icon="edit"
                          label="Edit price"
                          onClick={() => {
                            setPriceErrors({});
                            setPriceSelected(price);
                            setIsPriceFormOpen(true);
                          }}
                          className="mr-1 p-2 text-emerald-800 hover:bg-emerald-50"
                        />
                      )}
                      {profile?.permissions.includes('master_data.price_lists.delete') && (
                        <IconActionButton
                          icon="delete"
                          label="Delete price"
                          onClick={() => void deletePrice(price)}
                          className="p-2 text-rose-700 hover:bg-rose-50"
                        />
                      )}
                    </td>
                  </tr>
                ))}
                {prices.length === 0 && (
                  <tr>
                    <td colSpan={3} className="px-4 py-8 text-center text-slate-500">
                      No prices added yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}

export default function PriceListsPage() {
  return (
    <ProtectedPage>
      <PriceListsContent />
    </ProtectedPage>
  );
}