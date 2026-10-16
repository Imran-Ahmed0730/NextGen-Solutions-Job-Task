'use client';

import { useEffect, useMemo, useState } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { useSessionProfile } from '@/components/auth/session-shell';
import { apiRequest } from '@/lib/auth-api';
import { showErrorToast } from '@/lib/notifications';

type AuditEntry = {
  id: number;
  user_id: number | null;
  entity_type: string;
  entity_id: string;
  action: string;
  before_json: Record<string, unknown> | null;
  after_json: Record<string, unknown> | null;
  ip: string | null;
  created_at: string;
};

function AuditLogContent() {
  const canRead = useSessionProfile()?.permissions.includes('auth.audit_logs.read') ?? false;
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [filter, setFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!canRead) return;
    let active = true;
    apiRequest<AuditEntry[]>('/api/v1/auth/audit-logs?offset=0&limit=200')
      .then((result) => {
        if (active) setEntries(result);
      })
      .catch((cause: unknown) => {
        if (!active) return;
        const message = cause instanceof Error ? cause.message : 'Could not load audit log';
        setError(message);
        showErrorToast(message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [canRead]);

  const visibleEntries = useMemo(() => {
    const normalized = filter.trim().toLocaleLowerCase();
    if (!normalized) return entries;
    return entries.filter((entry) =>
      [
        entry.entity_type,
        entry.entity_id,
        entry.action,
        entry.user_id,
        entry.ip,
        entry.created_at,
      ]
        .filter(Boolean)
        .join(' ')
        .toLocaleLowerCase()
        .includes(normalized),
    );
  }, [entries, filter]);

  if (!canRead) {
    return (
      <section className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
        Your account does not have permission to view the audit log.
      </section>
    );
  }

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Audit Log</h1>
        <p className="mt-1 text-sm text-slate-600">
          Read-only history of recent changes and business actions.
        </p>
      </header>
      <label className="block max-w-xl text-sm font-medium text-slate-700">
        Search recent entries
        <input
          aria-label="Search audit entries"
          type="search"
          placeholder="Search entity, action, user ID, or IP"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2"
        />
      </label>
      {error && (
        <p role="alert" className="rounded-md bg-rose-50 p-3 text-sm text-rose-800">
          {error}
        </p>
      )}
      <section className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        {loading ? (
          <div aria-label="Loading audit log" role="status" className="animate-pulse p-5">
            {Array.from({ length: 6 }, (_, index) => (
              <div key={index} className="mb-4 h-8 rounded bg-slate-100" />
            ))}
          </div>
        ) : visibleEntries.length === 0 ? (
          <p className="p-5 text-sm text-slate-600">
            {entries.length ? 'No audit entries match your search.' : 'No audit entries found.'}
          </p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="px-4 py-3">Time</th>
                <th className="px-4 py-3">User</th>
                <th className="px-4 py-3">Action</th>
                <th className="px-4 py-3">Entity</th>
                <th className="px-4 py-3">Before / after</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {visibleEntries.map((entry) => (
                <tr key={entry.id} className="align-top">
                  <td className="whitespace-nowrap px-4 py-3">
                    {new Date(entry.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">{entry.user_id ?? 'System'}</td>
                  <td className="px-4 py-3">{entry.action}</td>
                  <td className="px-4 py-3">
                    {entry.entity_type} #{entry.entity_id}
                    {entry.ip && <span className="block text-xs text-slate-500">{entry.ip}</span>}
                  </td>
                  <td className="max-w-lg px-4 py-3">
                    <details>
                      <summary className="cursor-pointer text-emerald-800">View details</summary>
                      <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-words rounded bg-slate-50 p-3 text-xs">
                        {JSON.stringify(
                          { before: entry.before_json, after: entry.after_json },
                          null,
                          2,
                        )}
                      </pre>
                    </details>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      {!loading && entries.length === 200 && (
        <p className="text-xs text-slate-500">Showing the latest 200 audit records.</p>
      )}
    </section>
  );
}

export default function AuditLogsPage() {
  return (
    <ProtectedPage>
      <AuditLogContent />
    </ProtectedPage>
  );
}
