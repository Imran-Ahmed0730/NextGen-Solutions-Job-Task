'use client';

import { useCallback, useEffect, useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { useSessionProfile } from '@/components/auth/session-shell';
import { RequiredMark } from '@/components/forms/field-error';
import { SearchableSelect } from '@/components/forms/searchable-select';
import { apiRequest } from '@/lib/auth-api';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';
import { customerCollectionSchema } from '@/lib/auth-validation';

type Customer = { id: number; code: string; name: string };
type MoneyAccount = { id: number; name: string; type: string };
type CollectionOptions = { customers: Customer[]; accounts: MoneyAccount[] };
type Collection = {
  id: number;
  doc_no: string;
  doc_date: string;
  customer_id: number;
  account_id: number;
  amount: string;
  method_ref: string | null;
  status: string;
};

function today(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(
    now.getDate(),
  ).padStart(2, '0')}`;
}

function CustomerCollectionsContent() {
  const profile = useSessionProfile();
  const canRead = profile?.permissions.includes('money.collections.read') ?? false;
  const canCreate = profile?.permissions.includes('money.collections.create') ?? false;
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [accounts, setAccounts] = useState<MoneyAccount[]>([]);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [docDate, setDocDate] = useState(today);
  const [customerId, setCustomerId] = useState('');
  const [accountId, setAccountId] = useState('');
  const [amount, setAmount] = useState('');
  const [methodRef, setMethodRef] = useState('');
  const [note, setNote] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const reload = useCallback(async () => {
    const [options, collectionList] = await Promise.all([
      apiRequest<CollectionOptions>('/api/v1/money/collections/options'),
      apiRequest<Collection[]>('/api/v1/money/collections?limit=50'),
    ]);
    setCustomers(options.customers);
    setAccounts(options.accounts);
    setCollections(collectionList);
  }, []);

  useEffect(() => {
    if (!canRead) return;
    let active = true;
    setLoading(true);
    reload()
      .catch((cause: unknown) => {
        if (!active) return;
        const message = cause instanceof Error ? cause.message : 'Could not load collections';
        setError(message);
        showErrorToast(message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [canRead, reload]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = customerCollectionSchema.safeParse({
      doc_date: docDate,
      customer_id: Number(customerId),
      account_id: Number(accountId),
      amount,
      method_ref: methodRef,
      note,
    });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? 'Check the collection details.');
      return;
    }

    setError('');
    setSaving(true);
    try {
      const created = await apiRequest<Collection>('/api/v1/money/collections', {
        method: 'POST',
        body: JSON.stringify(parsed.data),
      });
      showSuccessToast(`Collection ${created.doc_no} posted.`);
      setDocDate(today());
      setCustomerId('');
      setAccountId('');
      setAmount('');
      setMethodRef('');
      setNote('');
      try {
        await reload();
      } catch (cause) {
        const message =
          cause instanceof Error
            ? `Collection posted, but history could not be refreshed: ${cause.message}`
            : 'Collection posted, but history could not be refreshed.';
        setError(message);
        showErrorToast(message);
      }
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not post the collection';
      setError(message);
      showErrorToast(message);
    } finally {
      setSaving(false);
    }
  }

  if (!canRead) {
    return <p className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">Your account does not have permission to view customer collections.</p>;
  }

  const customerName = (id: number) =>
    customers.find((customer) => customer.id === id)?.name ?? `Customer ${id}`;
  const accountName = (id: number) =>
    accounts.find((account) => account.id === id)?.name ?? `Account ${id}`;

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Customer Collections</h1>
        <p className="mt-1 text-sm text-slate-600">Record a customer payment into a cash, bank, or MFS account. Collections are recorded against the customer; invoice allocation will follow the sales module.</p>
      </header>

      {error && <p role="alert" className="rounded-md bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}

      {canCreate && (
        <form onSubmit={(event) => void submit(event)} className="grid gap-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm md:grid-cols-2">
          <label className="text-sm font-medium text-slate-700">
            Customer<RequiredMark />
            <SearchableSelect
              aria-label="Customer"
              required
              placeholder="Search customer by code or name"
              value={customerId}
              onChange={setCustomerId}
              options={customers.map((customer) => ({
                value: String(customer.id),
                label: `${customer.code} — ${customer.name}`,
                searchText: `${customer.code} ${customer.name}`,
              }))}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Money account<RequiredMark />
            <SearchableSelect
              aria-label="Money account"
              required
              placeholder="Search account"
              value={accountId}
              onChange={setAccountId}
              options={accounts.map((account) => ({
                value: String(account.id),
                label: `${account.name} — ${account.type}`,
                searchText: `${account.name} ${account.type}`,
              }))}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Collection date<RequiredMark />
            <input aria-label="Collection date" type="date" required value={docDate} onChange={(event) => setDocDate(event.target.value)} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Amount<RequiredMark />
            <input aria-label="Collection amount" type="number" min="0.01" step="0.01" required value={amount} onChange={(event) => setAmount(event.target.value)} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Payment reference
            <input aria-label="Payment reference" maxLength={100} value={methodRef} onChange={(event) => setMethodRef(event.target.value)} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Note
            <input aria-label="Collection note" maxLength={2000} value={note} onChange={(event) => setNote(event.target.value)} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
          </label>
          <div className="md:col-span-2">
            <button type="submit" disabled={saving} className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{saving ? 'Posting…' : 'Post collection'}</button>
          </div>
        </form>
      )}

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <h2 className="px-5 py-4 text-lg font-semibold text-slate-900">Recent collections</h2>
        {loading ? <p className="px-5 pb-5 text-sm text-slate-600">Loading collections…</p> : collections.length === 0 ? <p className="px-5 pb-5 text-sm text-slate-600">No collections have been posted.</p> : (
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-600"><tr><th className="px-5 py-3">Document</th><th className="px-5 py-3">Date</th><th className="px-5 py-3">Customer</th><th className="px-5 py-3">Account</th><th className="px-5 py-3 text-right">Amount</th></tr></thead>
            <tbody className="divide-y divide-slate-100">{collections.map((collection) => <tr key={collection.id}><td className="px-5 py-3 font-medium">{collection.doc_no}</td><td className="px-5 py-3">{collection.doc_date}</td><td className="px-5 py-3">{customerName(collection.customer_id)}</td><td className="px-5 py-3">{accountName(collection.account_id)}</td><td className="px-5 py-3 text-right">{collection.amount}</td></tr>)}</tbody>
          </table>
        )}
      </div>
    </section>
  );
}

export default function CustomerCollectionsPage() {
  return <ProtectedPage><CustomerCollectionsContent /></ProtectedPage>;
}
