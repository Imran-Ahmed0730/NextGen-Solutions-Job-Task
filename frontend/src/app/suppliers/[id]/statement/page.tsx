'use client';

import { useParams } from 'next/navigation';

import { ProtectedPage } from '@/components/auth/protected-page';
import { apiRequest } from '@/lib/auth-api';
import { showErrorToast } from '@/lib/notifications';
import { useEffect, useState } from 'react';

type SupplierStatement = {
  supplier_id: number;
  supplier_name: string;
  opening_due: string;
  balance: string;
  entries: Array<{
    date: string;
    type: string;
    description: string;
    amount: string;
    balance: string;
  }>;
};

export default function SupplierStatementPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id;
  const [statement, setStatement] = useState<SupplierStatement | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!id) return;
    apiRequest<SupplierStatement>(`/api/v1/suppliers/${id}/statement`)
      .then(setStatement)
      .catch((cause) =>
        setError(cause instanceof Error ? cause.message : 'Could not load supplier statement'),
      );
  }, [id]);

  return (
    <ProtectedPage>
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Supplier Statement</h1>
        {error && <p className="text-rose-700">{error}</p>}
        {statement && (
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <p className="font-medium text-slate-900">{statement.supplier_name}</p>
            <p className="mt-2 text-sm text-slate-600">Opening due: {Number(statement.opening_due).toFixed(2)}</p>
            <p className="text-sm font-semibold text-slate-900">Current balance: {Number(statement.balance).toFixed(2)}</p>
            <p className="mt-4 text-sm text-slate-600">
              This statement includes the opening balance, posted purchases and returns, and
              supplier payments.
            </p>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <th className="px-3 py-2">Date</th>
                    <th className="px-3 py-2">Entry</th>
                    <th className="px-3 py-2 text-right">Amount</th>
                    <th className="px-3 py-2 text-right">Balance</th>
                  </tr>
                </thead>
                <tbody>
                  {statement.entries.map((entry, index) => (
                    <tr key={`${entry.type}-${index}`} className="border-t border-slate-100">
                      <td className="px-3 py-2">{new Date(entry.date).toLocaleDateString()}</td>
                      <td className="px-3 py-2">{entry.description}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{Number(entry.amount).toFixed(2)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{Number(entry.balance).toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </ProtectedPage>
  );
}