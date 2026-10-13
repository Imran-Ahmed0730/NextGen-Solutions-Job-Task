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
  entries: Array<Record<string, unknown>>;
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
            <p className="mt-2 text-sm text-slate-600">Opening due: {statement.opening_due}</p>
            <p className="text-sm font-semibold text-slate-900">Balance: {statement.balance}</p>
            <p className="mt-4 text-sm text-slate-500">Entries will appear as purchases, receipts, and payments are implemented.</p>
          </div>
        )}
      </div>
    </ProtectedPage>
  );
}