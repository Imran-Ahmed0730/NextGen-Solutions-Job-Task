'use client';

import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { useSessionProfile } from '@/components/auth/session-shell';
import { RequiredMark } from '@/components/forms/field-error';
import { apiRequest } from '@/lib/auth-api';
import {
  payrollDeductionSchema,
  payrollPostSchema,
  payrollRunSchema,
} from '@/lib/auth-validation';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';

type PayrollLine = {
  id: number;
  employee_id: number;
  employee: { id: number; code: string; name: string; department: string | null };
  base_salary: string;
  deductions: string;
  net_pay: string;
  paid_txn_id: number | null;
};
type PayrollRun = {
  id: number;
  doc_no: string | null;
  period_month: number;
  period_year: number;
  status: 'DRAFT' | 'POSTED';
  total_amount: string;
  paid_on: string | null;
  account_id: number | null;
  lines: PayrollLine[];
};
type PayrollAccount = { id: number; name: string; type: string };

const monthNames = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
];

function localDate(): string {
  const current = new Date();
  return `${current.getFullYear()}-${String(current.getMonth() + 1).padStart(2, '0')}-${String(
    current.getDate(),
  ).padStart(2, '0')}`;
}

function PayrollContent() {
  const permissions = useSessionProfile()?.permissions ?? [];
  const canRead = permissions.includes('employees.payroll.read');
  const canCreate = permissions.includes('employees.payroll.create');
  const canUpdate = permissions.includes('employees.payroll.update');
  const canPost = permissions.includes('employees.payroll.post');
  const currentDate = localDate();
  const [runs, setRuns] = useState<PayrollRun[]>([]);
  const [accounts, setAccounts] = useState<PayrollAccount[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [deductions, setDeductions] = useState<Record<number, string>>({});
  const [periodMonth, setPeriodMonth] = useState(String(new Date().getMonth() + 1));
  const [periodYear, setPeriodYear] = useState(String(new Date().getFullYear()));
  const [accountId, setAccountId] = useState('');
  const [paidOn, setPaidOn] = useState(currentDate);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const selectedRun = useMemo(
    () => runs.find((run) => run.id === selectedId) ?? null,
    [runs, selectedId],
  );

  const reload = useCallback(async () => {
    const [options, runList] = await Promise.all([
      apiRequest<{ accounts: PayrollAccount[] }>('/api/v1/payroll/options'),
      apiRequest<PayrollRun[]>('/api/v1/payroll/runs?limit=100'),
    ]);
    setAccounts(options.accounts);
    setAccountId((current) => current || (options.accounts[0] ? String(options.accounts[0].id) : ''));
    setRuns(runList);
    setSelectedId((current) =>
      current && runList.some((run) => run.id === current) ? current : runList[0]?.id ?? null,
    );
  }, []);

  useEffect(() => {
    if (!canRead) return;
    let active = true;
    setLoading(true);
    reload()
      .catch((cause: unknown) => {
        if (!active) return;
        const message = cause instanceof Error ? cause.message : 'Could not load payroll';
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

  useEffect(() => {
    if (!selectedRun) {
      setDeductions({});
      return;
    }
    setDeductions(
      Object.fromEntries(selectedRun.lines.map((line) => [line.id, line.deductions])),
    );
  }, [selectedRun]);

  function applyRun(updated: PayrollRun) {
    setRuns((current) => [
      updated,
      ...current.filter((run) => run.id !== updated.id),
    ].sort((first, second) =>
      second.period_year - first.period_year || second.period_month - first.period_month,
    ));
    setSelectedId(updated.id);
    setDeductions(
      Object.fromEntries(updated.lines.map((line) => [line.id, line.deductions])),
    );
  }

  async function createRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = payrollRunSchema.safeParse({
      period_month: Number(periodMonth),
      period_year: Number(periodYear),
    });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? 'Enter a valid payroll period');
      return;
    }
    setError('');
    setBusy(true);
    try {
      const created = await apiRequest<PayrollRun>('/api/v1/payroll/runs', {
        method: 'POST',
        body: JSON.stringify(parsed.data),
      });
      applyRun(created);
      await reload();
      setSelectedId(created.id);
      showSuccessToast('Payroll draft created.');
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not create payroll draft';
      setError(message);
      showErrorToast(message);
    } finally {
      setBusy(false);
    }
  }

  async function saveDeduction(line: PayrollLine) {
    const parsed = payrollDeductionSchema.safeParse({
      deductions: deductions[line.id] ?? line.deductions,
    });
    if (!parsed.success || Number(parsed.data.deductions) > Number(line.base_salary)) {
      setError(
        parsed.success
          ? 'Deductions cannot exceed the employee’s base salary.'
          : (parsed.error.issues[0]?.message ?? 'Enter a valid deduction'),
      );
      return;
    }
    setError('');
    setBusy(true);
    try {
      const updated = await apiRequest<PayrollRun>(
        `/api/v1/payroll/runs/${selectedRun?.id}/lines/${line.id}`,
        { method: 'PATCH', body: JSON.stringify(parsed.data) },
      );
      applyRun(updated);
      showSuccessToast(`Deduction updated for ${line.employee.name}.`);
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not update deduction';
      setError(message);
      showErrorToast(message);
    } finally {
      setBusy(false);
    }
  }

  async function postRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedRun) return;
    const parsed = payrollPostSchema.safeParse({
      account_id: Number(accountId),
      paid_on: paidOn,
    });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? 'Check salary payment details');
      return;
    }
    setError('');
    setBusy(true);
    try {
      const posted = await apiRequest<PayrollRun>(
        `/api/v1/payroll/runs/${selectedRun.id}/post`,
        { method: 'POST', body: JSON.stringify(parsed.data) },
      );
      applyRun(posted);
      showSuccessToast(`Payroll ${posted.doc_no} posted and paid.`);
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not post payroll';
      setError(message);
      showErrorToast(message);
    } finally {
      setBusy(false);
    }
  }

  if (!canRead) {
    return (
      <p className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
        Your account does not have permission to view payroll.
      </p>
    );
  }

  return (
    <main className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Basic Payroll</h1>
        <p className="mt-1 text-sm text-slate-600">
          Prepare monthly base salaries, enter deductions, and post salary payments through Money.
        </p>
      </header>

      {error && <p role="alert" className="rounded-md bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}

      {canCreate && (
        <form
          onSubmit={(event) => void createRun(event)}
          className="flex flex-wrap items-end gap-4 rounded-xl border border-slate-200 bg-white p-5"
        >
          <label className="text-sm font-medium text-slate-700">
            Payroll month<RequiredMark />
            <select
              required
              value={periodMonth}
              onChange={(event) => setPeriodMonth(event.target.value)}
              className="mt-1 block rounded-md border border-slate-300 px-3 py-2"
            >
              {monthNames.map((month, index) => (
                <option key={month} value={index + 1}>{month}</option>
              ))}
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">
            Payroll year<RequiredMark />
            <input
              type="number"
              min="2000"
              max="9999"
              required
              placeholder="e.g. 2026"
              value={periodYear}
              onChange={(event) => setPeriodYear(event.target.value)}
              className="mt-1 block w-32 rounded-md border border-slate-300 px-3 py-2"
            />
          </label>
          <button
            type="submit"
            disabled={busy}
            className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
          >
            Create payroll draft
          </button>
        </form>
      )}

      <section className="grid gap-6 lg:grid-cols-[minmax(16rem,0.8fr)_minmax(0,1.7fr)]">
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="mb-3 text-lg font-medium">Payroll history</h2>
          {loading ? (
            <p className="text-sm text-slate-500">Loading payroll…</p>
          ) : runs.length === 0 ? (
            <p className="text-sm text-slate-500">No payroll runs yet.</p>
          ) : (
            <ul className="space-y-2">
              {runs.map((run) => (
                <li key={run.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(run.id)}
                    aria-pressed={selectedId === run.id}
                    className="w-full rounded-md border border-slate-200 p-3 text-left hover:bg-slate-50 aria-pressed:border-emerald-600"
                  >
                    <span className="block font-medium">
                      {monthNames[run.period_month - 1]} {run.period_year}
                    </span>
                    <span className="mt-1 block text-sm text-slate-600">
                      {run.status} · BDT {run.total_amount}
                    </span>
                    {run.doc_no && <span className="text-xs text-slate-500">{run.doc_no}</span>}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {selectedRun && (
          <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-lg font-medium">
                {monthNames[selectedRun.period_month - 1]} {selectedRun.period_year} payroll
              </h2>
              <p className="text-sm font-semibold">Net total: BDT {selectedRun.total_amount}</p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[680px] text-left text-sm">
                <thead className="border-b text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-2 py-2">Employee</th>
                    <th className="px-2 py-2">Base salary</th>
                    <th className="px-2 py-2">Deductions</th>
                    <th className="px-2 py-2">Net pay</th>
                    {selectedRun.status === 'POSTED' && <th className="px-2 py-2">Payment</th>}
                    {selectedRun.status === 'DRAFT' && canUpdate && <th className="px-2 py-2">Action</th>}
                  </tr>
                </thead>
                <tbody>
                  {selectedRun.lines.map((line) => (
                    <tr key={line.id} className="border-b last:border-0">
                      <td className="px-2 py-3">
                        <span className="block font-medium">{line.employee.name}</span>
                        <span className="text-xs text-slate-500">
                          {line.employee.code}{line.employee.department ? ` · ${line.employee.department}` : ''}
                        </span>
                      </td>
                      <td className="px-2 py-3">BDT {line.base_salary}</td>
                      <td className="px-2 py-3">
                        {selectedRun.status === 'DRAFT' && canUpdate ? (
                          <input
                            type="number"
                            min="0"
                            max={line.base_salary}
                            step="0.01"
                            placeholder="0.00"
                            aria-label={`Deductions for ${line.employee.name}`}
                            value={deductions[line.id] ?? line.deductions}
                            onChange={(event) =>
                              setDeductions((current) => ({
                                ...current,
                                [line.id]: event.target.value,
                              }))
                            }
                            className="w-32 rounded-md border border-slate-300 px-2 py-1"
                          />
                        ) : (
                          `BDT ${line.deductions}`
                        )}
                      </td>
                      <td className="px-2 py-3">BDT {line.net_pay}</td>
                      {selectedRun.status === 'POSTED' && (
                        <td className="px-2 py-3">
                          {line.paid_txn_id ? `Posted (#${line.paid_txn_id})` : 'No payment (zero net)'}
                        </td>
                      )}
                      {selectedRun.status === 'DRAFT' && canUpdate && (
                        <td className="px-2 py-3">
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => void saveDeduction(line)}
                            className="rounded border border-slate-300 px-2 py-1 text-xs disabled:opacity-60"
                          >
                            Save deduction
                          </button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {selectedRun.status === 'DRAFT' && canPost && (
              <form onSubmit={(event) => void postRun(event)} className="flex flex-wrap items-end gap-4 border-t pt-4">
                <label className="text-sm font-medium text-slate-700">
                  Pay from<RequiredMark />
                  <select
                    required
                    value={accountId}
                    onChange={(event) => setAccountId(event.target.value)}
                    className="mt-1 block min-w-48 rounded-md border border-slate-300 px-3 py-2"
                  >
                    <option value="">Choose a money account</option>
                    {accounts.map((account) => (
                      <option key={account.id} value={account.id}>
                        {account.name} ({account.type})
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-sm font-medium text-slate-700">
                  Payment date<RequiredMark />
                  <input
                    type="date"
                    required
                    value={paidOn}
                    onChange={(event) => setPaidOn(event.target.value)}
                    className="mt-1 block rounded-md border border-slate-300 px-3 py-2"
                  />
                </label>
                <button
                  type="submit"
                  disabled={busy || selectedRun.total_amount === '0.00' || accounts.length === 0}
                  className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
                >
                  Post salary payments
                </button>
              </form>
            )}
            {selectedRun.status === 'POSTED' && (
              <p className="border-t pt-3 text-sm text-slate-600">
                Paid {selectedRun.paid_on} from{' '}
                {accounts.find((account) => account.id === selectedRun.account_id)?.name ?? 'money account'}.
              </p>
            )}
          </section>
        )}
      </section>
    </main>
  );
}

export default function PayrollPage() {
  return (
    <ProtectedPage>
      <PayrollContent />
    </ProtectedPage>
  );
}
