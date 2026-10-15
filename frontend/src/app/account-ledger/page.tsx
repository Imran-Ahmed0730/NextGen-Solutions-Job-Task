'use client';

import { useEffect, useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { RequiredMark } from '@/components/forms/field-error';
import { SearchableSelect } from '@/components/forms/searchable-select';
import { useSessionProfile } from '@/components/auth/session-shell';
import { apiRequest } from '@/lib/auth-api';
import { showErrorToast } from '@/lib/notifications';

type AccountBalance = {
  account_id: number;
  account_name: string;
  account_type: string;
  opening_balance: string;
  balance: string;
};

type LedgerEntry = {
  id: number;
  txn_date: string;
  amount_signed: string;
  txn_type: string;
  source_type: string | null;
  source_id: number | null;
  party_type: string | null;
  party_id: number | null;
  note: string | null;
  running_balance: string;
};

type AccountLedger = {
  account_id: number;
  account_name: string;
  opening_balance: string;
  closing_balance: string;
  total_inflow: string;
  total_outflow: string;
  entries: LedgerEntry[];
};

function AccountLedgerContent() {
  const profile = useSessionProfile();
  const canRead = profile?.permissions.includes('money.transactions.read') ?? false;
  const [accounts, setAccounts] = useState<AccountBalance[]>([]);
  const [accountId, setAccountId] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [ledger, setLedger] = useState<AccountLedger | null>(null);
  const [loadingAccounts, setLoadingAccounts] = useState(true);
  const [loadingLedger, setLoadingLedger] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!canRead) return;
    let active = true;
    apiRequest<AccountBalance[]>('/api/v1/money-transactions/accounts')
      .then((result) => {
        if (active) setAccounts(result);
      })
      .catch((cause: unknown) => {
        if (!active) return;
        const message = cause instanceof Error ? cause.message : 'Could not load account balances';
        setError(message);
        showErrorToast(message);
      })
      .finally(() => {
        if (active) setLoadingAccounts(false);
      });
    return () => {
      active = false;
    };
  }, [canRead]);

  async function loadLedger(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!accountId) {
      setError('Select an account to view its ledger.');
      return;
    }
    if (dateFrom && dateTo && dateFrom > dateTo) {
      setError('Start date cannot be after end date.');
      return;
    }

    const params = new URLSearchParams();
    if (dateFrom) params.set('from_date', `${dateFrom}T00:00:00Z`);
    if (dateTo) params.set('to_date', `${dateTo}T23:59:59.999999Z`);
    setLoadingLedger(true);
    setError('');
    try {
      const query = params.size ? `?${params.toString()}` : '';
      const result = await apiRequest<AccountLedger>(
        `/api/v1/money-transactions/accounts/${accountId}/ledger${query}`,
      );
      setLedger(result);
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not load account ledger';
      setError(message);
      showErrorToast(message);
    } finally {
      setLoadingLedger(false);
    }
  }

  function selectAccount(value: string) {
    setAccountId(value);
    setLedger(null);
    setError('');
  }

  if (!canRead) {
    return (
      <section className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
        Your account does not have permission to view money account balances and ledgers.
      </section>
    );
  }

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Account Balances & Ledger</h1>
        <p className="mt-1 text-sm text-slate-600">
          Review current balances and the running cash book for each money account.
        </p>
      </header>

      {error && (
        <p role="alert" className="rounded-md bg-rose-50 p-3 text-sm text-rose-800">
          {error}
        </p>
      )}

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <h2 className="px-5 py-4 text-lg font-semibold text-slate-900">Current account balances</h2>
        {loadingAccounts ? (
          <p className="px-5 pb-5 text-sm text-slate-600">Loading account balances…</p>
        ) : accounts.length === 0 ? (
          <p className="px-5 pb-5 text-sm text-slate-600">No active money accounts found.</p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="px-5 py-3">Account</th>
                <th className="px-5 py-3">Type</th>
                <th className="px-5 py-3 text-right">Opening balance</th>
                <th className="px-5 py-3 text-right">Current balance</th>
                <th className="px-5 py-3">Ledger</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {accounts.map((account) => (
                <tr key={account.account_id}>
                  <td className="px-5 py-3 font-medium">{account.account_name}</td>
                  <td className="px-5 py-3">{account.account_type}</td>
                  <td className="px-5 py-3 text-right tabular-nums">{account.opening_balance}</td>
                  <td className="px-5 py-3 text-right tabular-nums font-semibold">{account.balance}</td>
                  <td className="px-5 py-3">
                    <button
                      type="button"
                      onClick={() => selectAccount(String(account.account_id))}
                      className="font-medium text-emerald-700 hover:underline"
                    >
                      View ledger
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <form
        onSubmit={(event) => void loadLedger(event)}
        className="grid gap-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm md:grid-cols-2 xl:grid-cols-4"
      >
        <label className="text-sm font-medium text-slate-700">
          Account<RequiredMark />
          <SearchableSelect
            aria-label="Account"
            required
            placeholder="Search money account"
            value={accountId}
            onChange={selectAccount}
            options={accounts.map((account) => ({
              value: String(account.account_id),
              label: `${account.account_name} — ${account.account_type}`,
              searchText: `${account.account_name} ${account.account_type}`,
            }))}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
          />
        </label>
        <label className="text-sm font-medium text-slate-700">
          From date
          <input
            aria-label="From date"
            type="date"
            value={dateFrom}
            onChange={(event) => setDateFrom(event.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
          />
        </label>
        <label className="text-sm font-medium text-slate-700">
          To date
          <input
            aria-label="To date"
            type="date"
            value={dateTo}
            onChange={(event) => setDateTo(event.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
          />
        </label>
        <button
          type="submit"
          disabled={loadingLedger || loadingAccounts}
          className="self-end rounded-md bg-emerald-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          {loadingLedger ? 'Loading…' : 'View ledger'}
        </button>
      </form>

      {ledger && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="grid gap-3 border-b border-slate-100 p-5 sm:grid-cols-2 lg:grid-cols-4">
            <div><p className="text-xs text-slate-500">Account</p><p className="font-medium">{ledger.account_name}</p></div>
            <div><p className="text-xs text-slate-500">Opening balance for period</p><p className="font-medium tabular-nums">{ledger.opening_balance}</p></div>
            <div><p className="text-xs text-slate-500">Inflow / Outflow</p><p className="font-medium tabular-nums">{ledger.total_inflow} / {ledger.total_outflow}</p></div>
            <div><p className="text-xs text-slate-500">Closing balance</p><p className="font-semibold tabular-nums">{ledger.closing_balance}</p></div>
          </div>
          {ledger.entries.length === 0 ? (
            <p className="p-5 text-sm text-slate-600">No transactions found for this account and date range.</p>
          ) : (
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="px-4 py-3">Date</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Reference</th>
                  <th className="px-4 py-3">Note</th>
                  <th className="px-4 py-3 text-right">Amount</th>
                  <th className="px-4 py-3 text-right">Running balance</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {ledger.entries.map((entry) => (
                  <tr key={entry.id}>
                    <td className="whitespace-nowrap px-4 py-3">{new Date(entry.txn_date).toLocaleString()}</td>
                    <td className="px-4 py-3">{entry.txn_type}</td>
                    <td className="px-4 py-3">
                      {entry.source_type
                        ? `${entry.source_type}${entry.source_id === null ? '' : ` #${entry.source_id}`}`
                        : '—'}
                    </td>
                    <td className="px-4 py-3">{entry.note ?? '—'}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{entry.amount_signed}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{entry.running_balance}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </section>
  );
}

export default function AccountLedgerPage() {
  return (
    <ProtectedPage>
      <AccountLedgerContent />
    </ProtectedPage>
  );
}
