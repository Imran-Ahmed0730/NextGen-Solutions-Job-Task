'use client';

import { FormEvent, useEffect, useState } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { useSessionProfile } from '@/components/auth/session-shell';
import { apiRequest } from '@/lib/auth-api';
import { showErrorToast } from '@/lib/notifications';

type Dashboard = {
  period_from: string;
  period_to: string;
  sales: string | number;
  collections: string | number;
  expenses: string | number;
  purchases: string | number;
  account_balances: Record<string, string | number>;
  customer_due: string | number;
  supplier_due: string | number;
  inventory_value: string | number;
  pending_orders: number;
  estimated_profit: string | number;
};

function localDateString(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function formatAmount(value: string | number | undefined): string {
  return new Intl.NumberFormat(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(value ?? 0));
}

function DashboardSkeleton() {
  return (
    <div
      aria-label="Loading dashboard"
      role="status"
      className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3"
    >
      {Array.from({ length: 10 }, (_, index) => (
        <div
          key={index}
          className="animate-pulse rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
        >
          <div className="h-4 w-2/5 rounded bg-slate-200" />
          <div className="mt-4 h-8 w-3/5 rounded bg-slate-100" />
        </div>
      ))}
    </div>
  );
}

function DashboardContent() {
  const permissions = useSessionProfile()?.permissions ?? [];
  const canRead = permissions.includes('reports.dashboard.read');
  const today = localDateString(new Date());
  const [periodFrom, setPeriodFrom] = useState(today);
  const [periodTo, setPeriodTo] = useState(today);
  const [appliedPeriod, setAppliedPeriod] = useState({ from: today, to: today });
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!canRead) return;
    let active = true;
    setLoading(true);
    const params = new URLSearchParams({
      period_from: appliedPeriod.from,
      period_to: appliedPeriod.to,
    });
    apiRequest<Dashboard>(`/api/v1/reports/dashboard?${params.toString()}`)
      .then((result) => {
        if (active) {
          setDashboard(result);
          setError('');
        }
      })
      .catch((cause: unknown) => {
        if (!active) return;
        const message = cause instanceof Error ? cause.message : 'Could not load dashboard';
        setError(message);
        showErrorToast(message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [canRead, appliedPeriod]);

  function validatePeriod(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (periodFrom > periodTo) {
      const message = 'Start date cannot be after end date.';
      setError(message);
      showErrorToast(message);
      return;
    }
    setError('');
    setAppliedPeriod({ from: periodFrom, to: periodTo });
  }

  if (!canRead) {
    return (
      <section className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
        Your account does not have permission to view the management dashboard.
      </section>
    );
  }

  const money = dashboard?.account_balances ?? {};
  const cards = [
    { label: 'Sales', value: formatAmount(dashboard?.sales) },
    { label: 'Customer collections', value: formatAmount(dashboard?.collections) },
    { label: 'Expenses', value: formatAmount(dashboard?.expenses) },
    { label: 'Purchases', value: formatAmount(dashboard?.purchases) },
    {
      label: 'Cash / Bank / MFS balances',
      value: null,
    },
    { label: 'Customer due', value: formatAmount(dashboard?.customer_due) },
    { label: 'Supplier due', value: formatAmount(dashboard?.supplier_due) },
    { label: 'Inventory value', value: formatAmount(dashboard?.inventory_value) },
    { label: 'Pending orders', value: String(dashboard?.pending_orders ?? 0) },
    { label: 'Estimated profit', value: formatAmount(dashboard?.estimated_profit) },
  ];

  return (
    <section className="space-y-6">
      <header>
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-emerald-700">
          Sabuj Pran
        </p>
        <h1 className="mt-2 text-3xl font-semibold text-slate-900">Management Dashboard</h1>
        <p className="mt-2 text-sm text-slate-600">
          Period activity and current business balances, calculated from posted records.
        </p>
      </header>

      <form
        onSubmit={validatePeriod}
        className="grid gap-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:grid-cols-[1fr_1fr_auto]"
      >
        <label className="text-sm font-medium text-slate-700">
          From date
          <input
            aria-label="From date"
            type="date"
            value={periodFrom}
            onChange={(event) => setPeriodFrom(event.target.value)}
            className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2"
          />
        </label>
        <label className="text-sm font-medium text-slate-700">
          To date
          <input
            aria-label="To date"
            type="date"
            value={periodTo}
            onChange={(event) => setPeriodTo(event.target.value)}
            className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2"
          />
        </label>
        <button
          type="submit"
          className="self-end rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-800"
        >
          Apply period
        </button>
      </form>

      {error && (
        <p role="alert" className="rounded-md bg-rose-50 p-3 text-sm text-rose-800">
          {error}
        </p>
      )}
      {loading ? (
        <DashboardSkeleton />
      ) : dashboard ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {cards.map((card) => (
            <article
              key={card.label}
              className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <h2 className="text-sm font-medium text-slate-600">{card.label}</h2>
              {card.value === null ? (
                <dl className="mt-3 grid grid-cols-3 gap-2 text-sm">
                  {(['CASH', 'BANK', 'MFS'] as const).map((type) => (
                    <div key={type}>
                      <dt className="text-xs text-slate-500">{type}</dt>
                      <dd className="mt-1 font-semibold tabular-nums">
                        {formatAmount(money[type])}
                      </dd>
                    </div>
                  ))}
                </dl>
              ) : (
                <p className="mt-3 text-2xl font-semibold tabular-nums text-slate-900">
                  {card.value}
                </p>
              )}
            </article>
          ))}
        </div>
      ) : null}
      {dashboard && (
        <p className="text-xs text-slate-500">
          Activity period: {dashboard.period_from} to {dashboard.period_to}. Due, inventory, and
          account balances are current totals.
        </p>
      )}
    </section>
  );
}

export default function Home() {
  return (
    <ProtectedPage>
      <DashboardContent />
    </ProtectedPage>
  );
}
