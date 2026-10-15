'use client';

import { useCallback, useEffect, useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { useSessionProfile } from '@/components/auth/session-shell';
import { RequiredMark } from '@/components/forms/field-error';
import { SearchableSelect } from '@/components/forms/searchable-select';
import { apiRequest } from '@/lib/auth-api';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';
import { expenseSchema } from '@/lib/auth-validation';

type ExpenseCategory = { id: number; name: string };
type MoneyAccount = { id: number; name: string; type: string };
type ExpenseOptions = { categories: ExpenseCategory[]; accounts: MoneyAccount[] };
type Expense = {
  id: number;
  doc_no: string;
  doc_date: string;
  category_id: number;
  account_id: number;
  amount: string;
  paid_to: string | null;
  status: string;
  note: string | null;
};

function today(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(
    now.getDate(),
  ).padStart(2, '0')}`;
}

function ExpensesContent() {
  const profile = useSessionProfile();
  const canRead = profile?.permissions.includes('money.expenses.read') ?? false;
  const canCreate = profile?.permissions.includes('money.expenses.create') ?? false;
  const [categories, setCategories] = useState<ExpenseCategory[]>([]);
  const [accounts, setAccounts] = useState<MoneyAccount[]>([]);
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [docDate, setDocDate] = useState(today);
  const [categoryId, setCategoryId] = useState('');
  const [accountId, setAccountId] = useState('');
  const [amount, setAmount] = useState('');
  const [paidTo, setPaidTo] = useState('');
  const [note, setNote] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const reload = useCallback(async () => {
    const [options, expenseList] = await Promise.all([
      apiRequest<ExpenseOptions>('/api/v1/expenses/options'),
      apiRequest<Expense[]>('/api/v1/expenses?limit=50'),
    ]);
    setCategories(options.categories);
    setAccounts(options.accounts);
    setExpenses(expenseList);
  }, []);

  useEffect(() => {
    if (!canRead) return;
    let active = true;
    setLoading(true);
    reload()
      .catch((cause: unknown) => {
        if (!active) return;
        const message = cause instanceof Error ? cause.message : 'Could not load expenses';
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
    const parsed = expenseSchema.safeParse({
      doc_date: docDate,
      category_id: Number(categoryId),
      account_id: Number(accountId),
      amount,
      paid_to: paidTo ? paidTo.trim() : undefined,
      note: note ? note.trim() : undefined,
    });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? 'Check the expense details.');
      return;
    }

    setError('');
    setSaving(true);
    try {
      const created = await apiRequest<Expense>('/api/v1/expenses', {
        method: 'POST',
        body: JSON.stringify(parsed.data),
      });
      showSuccessToast(`Expense ${created.doc_no} recorded successfully.`);
      setAmount('');
      setPaidTo('');
      setNote('');
      await reload();
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not save expense';
      setError(message);
      showErrorToast(message);
    } finally {
      setSaving(false);
    }
  }

  if (!canRead) {
    return (
      <section className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
        Your account does not have permission to view expenses.
      </section>
    );
  }

  const categoryName = (id: number) =>
    categories.find((c) => c.id === id)?.name ?? `Category ${id}`;
  const accountName = (id: number) =>
    accounts.find((a) => a.id === id)?.name ?? `Account ${id}`;

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Expenses</h1>
        <p className="mt-1 text-sm text-slate-600">
          Record company operational expenses paid from cash, bank, or mobile accounts.
        </p>
      </header>

      {canCreate && (
        <form
          onSubmit={(e) => void submit(e)}
          className="space-y-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
        >
          <h2 className="text-lg font-semibold text-slate-900">Record Expense</h2>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <label className="text-sm font-medium text-slate-700">
              Document date<RequiredMark />
              <input
                aria-label="Document date"
                type="date"
                required
                value={docDate}
                onChange={(e) => setDocDate(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Expense category<RequiredMark />
              <SearchableSelect
                aria-label="Expense category"
                required
                placeholder="Select expense category"
                value={categoryId}
                onChange={setCategoryId}
                options={categories.map((c) => ({
                  value: String(c.id),
                  label: c.name,
                }))}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Paid from account<RequiredMark />
              <SearchableSelect
                aria-label="Paid from account"
                required
                placeholder="Select account"
                value={accountId}
                onChange={setAccountId}
                options={accounts.map((a) => ({
                  value: String(a.id),
                  label: `${a.name} (${a.type})`,
                }))}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Amount (BDT)<RequiredMark />
              <input
                aria-label="Amount"
                type="number"
                min="0.01"
                step="0.01"
                required
                placeholder="0.00"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Paid to
              <input
                aria-label="Paid to"
                type="text"
                placeholder="Recipient or payee name"
                value={paidTo}
                onChange={(e) => setPaidTo(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
            <label className="text-sm font-medium text-slate-700 md:col-span-2 lg:col-span-3">
              Note
              <input
                aria-label="Note"
                type="text"
                placeholder="Optional description"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
          </div>
          {error && (
            <p role="alert" className="rounded-md bg-rose-50 p-3 text-sm text-rose-800">
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={saving}
            className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-800 disabled:opacity-60"
          >
            {saving ? 'Recording…' : 'Record expense'}
          </button>
        </form>
      )}

      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 px-5 py-4">
          <h2 className="font-semibold text-slate-900">Recent expenses</h2>
        </div>
        {loading ? (
          <p className="p-5 text-sm text-slate-600">Loading expenses…</p>
        ) : expenses.length === 0 ? (
          <p className="p-5 text-sm text-slate-600">No expenses recorded yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-600">
                <tr>
                  <th className="px-4 py-3">Document</th>
                  <th className="px-4 py-3">Date</th>
                  <th className="px-4 py-3">Category</th>
                  <th className="px-4 py-3">Account</th>
                  <th className="px-4 py-3">Paid To</th>
                  <th className="px-4 py-3 text-right">Amount</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Note</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {expenses.map((item) => (
                  <tr key={item.id}>
                    <td className="px-4 py-3 font-medium text-slate-900">{item.doc_no}</td>
                    <td className="px-4 py-3">{item.doc_date}</td>
                    <td className="px-4 py-3">{categoryName(item.category_id)}</td>
                    <td className="px-4 py-3">{accountName(item.account_id)}</td>
                    <td className="px-4 py-3">{item.paid_to || '—'}</td>
                    <td className="px-4 py-3 text-right font-medium text-rose-700">
                      -{item.amount}
                    </td>
                    <td className="px-4 py-3">
                      <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-800">
                        {item.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-600">{item.note || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </section>
  );
}

export default function ExpensesPage() {
  return (
    <ProtectedPage>
      <ExpensesContent />
    </ProtectedPage>
  );
}

