'use client';

import { useParams } from 'next/navigation';

import { ProtectedPage } from '@/components/auth/protected-page';
import { apiRequest } from '@/lib/auth-api';
import { showErrorToast } from '@/lib/notifications';
import { useEffect, useState } from 'react';

type CustomerStatement = {
  customer_id: number;
  customer_name: string;
  opening_due: string;
  balance: string;
  entries: Array<Record<string, unknown>>;
};

export default function CustomerStatementPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id;
  const [statement, setStatement] = useState<CustomerStatement | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!id) return;
    apiRequest<CustomerStatement>(`/api/v1/customers/${id}/statement`)
      .then(setStatement)
      .catch((cause) =>
        setError(cause instanceof Error ? cause.message : 'Could not load customer statement'),
      );
  }, [id]);

  return (
    <ProtectedPage>
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Customer Statement</h1>
        {error && <p className="text-rose-700">{error}</p>}
        {statement && (
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <p className="font-medium text-slate-900">{statement.customer_name}</p>
            <p className="mt-2 text-sm text-slate-600">Opening due: {statement.opening_due}</p>
            <p className="text-sm font-semibold text-slate-900">Balance: {statement.balance}</p>
            <p className="mt-4 text-sm text-slate-500">Entries will appear as sales, deliveries, invoices, and collections are implemented.</p>
          </div>
        )}
      </div>
    </ProtectedPage>
  );
}