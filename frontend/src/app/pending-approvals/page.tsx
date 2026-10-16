'use client';

import { useCallback, useEffect, useState } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { useSessionProfile } from '@/components/auth/session-shell';
import { apiRequest } from '@/lib/auth-api';
import { documentTypeLabel, statusLabel } from '@/lib/display-labels';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';

type PendingApproval = {
  id: number;
  doc_type: string;
  doc_id: number;
  doc_no: string;
  doc_status: string;
  amount: string;
  requested_by: number;
  requester_name: string;
  approver_role_id: number;
  approver_role_name: string;
  requested_at: string;
  status: string;
};

function PendingApprovalsContent() {
  const permissions = useSessionProfile()?.permissions ?? [];
  const canRead = permissions.includes('approvals.requests.read');
  const canDecide = permissions.includes('approvals.requests.decide');
  const [requests, setRequests] = useState<PendingApproval[]>([]);
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState('');

  const reload = useCallback(async () => {
    setRequests(await apiRequest<PendingApproval[]>('/api/v1/approvals/requests?limit=100'));
  }, []);

  useEffect(() => {
    if (!canRead) return;
    let active = true;
    setLoading(true);
    reload()
      .catch((cause: unknown) => {
        if (!active) return;
        const message = cause instanceof Error ? cause.message : 'Could not load approvals';
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

  async function decide(id: number, action: 'approve' | 'reject') {
    setBusyId(id);
    setError('');
    try {
      await apiRequest<PendingApproval>(`/api/v1/approvals/requests/${id}/${action}`, {
        method: 'POST',
        body: JSON.stringify({ note: notes[id]?.trim() || null }),
      });
      showSuccessToast(action === 'approve' ? 'Approval recorded.' : 'Request rejected.');
      await reload();
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not decide approval';
      setError(message);
      showErrorToast(message);
    } finally {
      setBusyId(null);
    }
  }

  if (!canRead) {
    return (
      <p className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
        Your account does not have permission to view pending approvals.
      </p>
    );
  }

  return (
    <main className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Pending Approvals</h1>
        <p className="mt-1 text-sm text-slate-600">
          Review documents assigned to your role. You cannot approve your own requests.
        </p>
      </header>
      {error && (
        <p role="alert" className="rounded-md bg-rose-50 p-3 text-sm text-rose-800">
          {error}
        </p>
      )}
      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        {loading ? (
          <p className="p-5 text-sm text-slate-600">Loading pending approvals…</p>
        ) : requests.length === 0 ? (
          <p className="p-5 text-sm text-slate-600">There are no pending approvals for your roles.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-600">
                <tr>
                  <th className="px-4 py-3">Document</th>
                  <th className="px-4 py-3">Requested by</th>
                  <th className="px-4 py-3 text-right">Amount</th>
                  <th className="px-4 py-3">Approver role</th>
                  <th className="px-4 py-3">Decision note</th>
                  {canDecide && <th className="px-4 py-3">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {requests.map((item) => (
                  <tr key={item.id}>
                    <td className="px-4 py-4">
                      <p className="font-medium text-slate-900">{item.doc_no}</p>
                      <p className="text-xs text-slate-600">
                        {documentTypeLabel(item.doc_type)} · {statusLabel(item.doc_status)}
                      </p>
                    </td>
                    <td className="px-4 py-4">{item.requester_name}</td>
                    <td className="px-4 py-4 text-right tabular-nums">{item.amount}</td>
                    <td className="px-4 py-4">{item.approver_role_name}</td>
                    <td className="px-4 py-4">
                      <input
                        type="text"
                        aria-label={`Decision note for ${item.doc_no}`}
                        placeholder="Optional note"
                        value={notes[item.id] ?? ''}
                        onChange={(event) =>
                          setNotes((current) => ({ ...current, [item.id]: event.target.value }))
                        }
                        disabled={!canDecide || busyId === item.id}
                        className="w-56 rounded-md border border-slate-300 px-3 py-2"
                      />
                    </td>
                    {canDecide && (
                      <td className="space-x-2 whitespace-nowrap px-4 py-4">
                        <button
                          type="button"
                          disabled={busyId === item.id}
                          onClick={() => void decide(item.id, 'approve')}
                          className="rounded-md bg-emerald-700 px-3 py-2 text-xs font-medium text-white disabled:opacity-60"
                        >
                          Approve
                        </button>
                        <button
                          type="button"
                          disabled={busyId === item.id}
                          onClick={() => void decide(item.id, 'reject')}
                          className="rounded-md border border-rose-300 px-3 py-2 text-xs font-medium text-rose-800 disabled:opacity-60"
                        >
                          Reject
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}

export default function PendingApprovalsPage() {
  return (
    <ProtectedPage>
      <PendingApprovalsContent />
    </ProtectedPage>
  );
}
