'use client';

import { useEffect, useState } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { apiRequest } from '@/lib/auth-api';
import { showErrorToast } from '@/lib/notifications';

type PermissionRecord = {
  id: number;
  code: string;
  module: string;
  description: string | null;
};

export default function PermissionsPage() {
  const [permissions, setPermissions] = useState<PermissionRecord[]>([]);
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    apiRequest<PermissionRecord[]>('/api/v1/auth/permissions')
      .then(setPermissions)
      .catch((cause: unknown) => {
        setLoadFailed(true);
        showErrorToast(cause instanceof Error ? cause.message : 'Could not load permissions');
      });
  }, []);

  return (
    <ProtectedPage>
      <h1 className="text-2xl font-semibold">Permissions</h1>
      <p className="mt-1 text-sm text-slate-600">The system permission catalog is maintained by the application.</p>
      <div className="mt-6 overflow-x-auto rounded-lg border border-slate-200">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr><th className="px-4 py-3">Permission</th><th className="px-4 py-3">Module</th><th className="px-4 py-3">Description</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {permissions.map((permission) => (
              <tr key={permission.id}>
                <td className="px-4 py-3 font-mono text-xs">{permission.code}</td>
                <td className="px-4 py-3">{permission.module}</td>
                <td className="px-4 py-3">{permission.description ?? '—'}</td>
              </tr>
            ))}
            {permissions.length === 0 && <tr><td colSpan={3} className="px-4 py-8 text-center text-slate-500">{loadFailed ? 'Permissions could not be loaded.' : 'No permissions have been seeded yet.'}</td></tr>}
          </tbody>
        </table>
      </div>
    </ProtectedPage>
  );
}
