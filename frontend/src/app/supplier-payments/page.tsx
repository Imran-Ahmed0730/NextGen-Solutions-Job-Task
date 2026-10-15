'use client';

import { useCallback, useEffect, useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { useSessionProfile } from '@/components/auth/session-shell';
import { RequiredMark } from '@/components/forms/field-error';
import { SearchableSelect } from '@/components/forms/searchable-select';
import { apiRequest } from '@/lib/auth-api';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';
import { moneyAmountToCents, supplierPaymentSchema } from '@/lib/auth-validation';

type Supplier = { id: number; code: string; name: string };
type MoneyAccount = { id: number; name: string; type: string };
type PaymentOptions = { suppliers: Supplier[]; accounts: MoneyAccount[] };
type Bill = {
  ref_type: 'RECEIPT' | 'DIRECT_PURCHASE';
  ref_id: number;
  doc_no: string;
  doc_date: string;
  total: string;
  paid: string;
  outstanding: string;
};
type Allocation = { ref_type: Bill['ref_type']; ref_id: number; amount: string };
type Payment = {
  id: number;
  doc_no: string;
  doc_date: string;
  supplier_id: number;
  account_id: number;
  amount: string;
  allocations: Allocation[];
};

function today(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(
    now.getDate(),
  ).padStart(2, '0')}`;
}

function SupplierPaymentsContent() {
  const profile = useSessionProfile();
  const canRead = profile?.permissions.includes('money.supplier_payments.read') ?? false;
  const canCreate = profile?.permissions.includes('money.supplier_payments.create') ?? false;
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [accounts, setAccounts] = useState<MoneyAccount[]>([]);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [bills, setBills] = useState<Bill[]>([]);
  const [docDate, setDocDate] = useState(today);
  const [supplierId, setSupplierId] = useState('');
  const [accountId, setAccountId] = useState('');
  const [amount, setAmount] = useState('');
  const [note, setNote] = useState('');
  const [allocations, setAllocations] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const reload = useCallback(async () => {
    const [options, paymentList] = await Promise.all([
      apiRequest<PaymentOptions>('/api/v1/money/supplier-payments/options'),
      apiRequest<Payment[]>('/api/v1/money/supplier-payments?limit=50'),
    ]);
    setSuppliers(options.suppliers);
    setAccounts(options.accounts);
    setPayments(paymentList);
  }, []);

  useEffect(() => {
    if (!canRead) return;
    let active = true;
    setLoading(true);
    reload()
      .catch((cause: unknown) => {
        if (!active) return;
        const message = cause instanceof Error ? cause.message : 'Could not load supplier payments';
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
    setBills([]);
    setAllocations({});
    if (!supplierId || !canRead) return;
    let active = true;
    apiRequest<Bill[]>(`/api/v1/money/supplier-payments/bills?supplier_id=${supplierId}`)
      .then((billList) => {
        if (active) setBills(billList);
      })
      .catch((cause: unknown) => {
        if (!active) return;
        const message = cause instanceof Error ? cause.message : 'Could not load supplier bills';
        setError(message);
        showErrorToast(message);
      });
    return () => {
      active = false;
    };
  }, [canRead, supplierId]);

  function updateAllocation(bill: Bill, value: string) {
    const key = `${bill.ref_type}:${bill.ref_id}`;
    setAllocations((current) => ({ ...current, [key]: value }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const billAllocations = bills.flatMap((bill) => {
      const value = allocations[`${bill.ref_type}:${bill.ref_id}`] ?? '';
      return value ? [{ ref_type: bill.ref_type, ref_id: bill.ref_id, amount: value }] : [];
    });
    const allocationExceedingOutstanding = billAllocations.find((allocation) => {
      const bill = bills.find(
        (candidate) =>
          candidate.ref_type === allocation.ref_type && candidate.ref_id === allocation.ref_id,
      );
      const allocationCents = moneyAmountToCents(allocation.amount);
      const outstandingCents = bill ? moneyAmountToCents(bill.outstanding) : null;
      return (
        bill !== undefined &&
        allocationCents !== null &&
        outstandingCents !== null &&
        allocationCents > outstandingCents
      );
    });
    if (allocationExceedingOutstanding) {
      setError('A bill allocation cannot exceed its outstanding amount.');
      return;
    }
    const parsed = supplierPaymentSchema.safeParse({
      doc_date: docDate,
      supplier_id: Number(supplierId),
      account_id: Number(accountId),
      amount,
      note,
      allocations: billAllocations,
    });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? 'Check the payment details.');
      return;
    }

    setError('');
    setSaving(true);
    try {
      const created = await apiRequest<Payment>('/api/v1/money/supplier-payments', {
        method: 'POST',
        body: JSON.stringify(parsed.data),
      });
      showSuccessToast(`Supplier payment ${created.doc_no} posted.`);
      setDocDate(today());
      setSupplierId('');
      setAccountId('');
      setAmount('');
      setNote('');
      setBills([]);
      setAllocations({});
      try {
        await reload();
      } catch (cause) {
        const message =
          cause instanceof Error
            ? `Payment posted, but history could not be refreshed: ${cause.message}`
            : 'Payment posted, but history could not be refreshed.';
        setError(message);
        showErrorToast(message);
      }
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not post supplier payment';
      setError(message);
      showErrorToast(message);
    } finally {
      setSaving(false);
    }
  }

  if (!canRead) {
    return <p className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">Your account does not have permission to view supplier payments.</p>;
  }

  const supplierName = (id: number) =>
    suppliers.find((supplier) => supplier.id === id)?.name ?? `Supplier ${id}`;
  const accountName = (id: number) =>
    accounts.find((account) => account.id === id)?.name ?? `Account ${id}`;

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Supplier Payments</h1>
        <p className="mt-1 text-sm text-slate-600">Record a supplier payment and optionally allocate it to outstanding goods receipts or direct purchases. Any unallocated amount remains against the supplier balance.</p>
      </header>

      {error && <p role="alert" className="rounded-md bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}

      {canCreate && (
        <form onSubmit={(event) => void submit(event)} className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="grid gap-4 md:grid-cols-2">
            <label className="text-sm font-medium text-slate-700">
              Supplier<RequiredMark />
              <SearchableSelect
                aria-label="Supplier"
                required
                placeholder="Search supplier by code or name"
                value={supplierId}
                onChange={setSupplierId}
                options={suppliers.map((supplier) => ({
                  value: String(supplier.id),
                  label: `${supplier.code} — ${supplier.name}`,
                  searchText: `${supplier.code} ${supplier.name}`,
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
              Payment date<RequiredMark />
              <input aria-label="Payment date" type="date" required value={docDate} onChange={(event) => setDocDate(event.target.value)} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Amount<RequiredMark />
              <input aria-label="Payment amount" type="number" min="0.01" step="0.01" required value={amount} onChange={(event) => setAmount(event.target.value)} placeholder="0.00" className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
            </label>
            <label className="text-sm font-medium text-slate-700 md:col-span-2">
              Note
              <input aria-label="Payment note" maxLength={2000} value={note} onChange={(event) => setNote(event.target.value)} placeholder="Optional payment note" className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
            </label>
          </div>

          {supplierId && (
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <h2 className="px-4 py-3 text-sm font-semibold text-slate-800">Allocate to outstanding bills (optional)</h2>
              {bills.length === 0 ? <p className="px-4 pb-4 text-sm text-slate-600">No outstanding receipts or direct purchases.</p> : (
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 text-slate-600"><tr><th className="px-4 py-2">Bill</th><th className="px-4 py-2">Date</th><th className="px-4 py-2 text-right">Outstanding</th><th className="px-4 py-2">Allocate amount</th></tr></thead>
                  <tbody className="divide-y divide-slate-100">{bills.map((bill) => <tr key={`${bill.ref_type}:${bill.ref_id}`}><td className="px-4 py-2">{bill.doc_no} ({bill.ref_type === 'RECEIPT' ? 'Goods receipt' : 'Direct purchase'})</td><td className="px-4 py-2">{bill.doc_date}</td><td className="px-4 py-2 text-right">{bill.outstanding}</td><td className="px-4 py-2"><input aria-label={`Allocate to ${bill.doc_no}`} type="number" min="0.01" max={bill.outstanding} step="0.01" value={allocations[`${bill.ref_type}:${bill.ref_id}`] ?? ''} onChange={(event) => updateAllocation(bill, event.target.value)} placeholder="0.00" className="w-36 rounded-md border border-slate-300 px-2 py-1" /></td></tr>)}</tbody>
                </table>
              )}
            </div>
          )}

          <button type="submit" disabled={saving} className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{saving ? 'Posting…' : 'Post supplier payment'}</button>
        </form>
      )}

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <h2 className="px-5 py-4 text-lg font-semibold text-slate-900">Recent supplier payments</h2>
        {loading ? <p className="px-5 pb-5 text-sm text-slate-600">Loading payments…</p> : payments.length === 0 ? <p className="px-5 pb-5 text-sm text-slate-600">No supplier payments have been posted.</p> : (
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-600"><tr><th className="px-5 py-3">Document</th><th className="px-5 py-3">Date</th><th className="px-5 py-3">Supplier</th><th className="px-5 py-3">Account</th><th className="px-5 py-3 text-right">Amount</th></tr></thead>
            <tbody className="divide-y divide-slate-100">{payments.map((payment) => <tr key={payment.id}><td className="px-5 py-3 font-medium">{payment.doc_no}</td><td className="px-5 py-3">{payment.doc_date}</td><td className="px-5 py-3">{supplierName(payment.supplier_id)}</td><td className="px-5 py-3">{accountName(payment.account_id)}</td><td className="px-5 py-3 text-right">{payment.amount}</td></tr>)}</tbody>
          </table>
        )}
      </div>
    </section>
  );
}

export default function SupplierPaymentsPage() {
  return <ProtectedPage><SupplierPaymentsContent /></ProtectedPage>;
}
