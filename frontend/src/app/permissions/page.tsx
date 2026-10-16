'use client';

import { Fragment } from 'react';
import { useEffect, useState } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { apiRequest } from '@/lib/auth-api';
import { moduleLabel, permissionLabel } from '@/lib/display-labels';
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
  const permissionsByModule = permissions.reduce<Record<string, PermissionRecord[]>>(
    (groups, permission) => {
      (groups[permission.module] ??= []).push(permission);
      return groups;
    },
    {},
  );

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
            <tr><th className="px-4 py-3">Allowed task</th><th className="px-4 py-3">Work area</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {Object.entries(permissionsByModule).map(([module, modulePermissions]) => (
              <Fragment key={module}>
                <tr className="bg-slate-50">
                  <th colSpan={2} className="px-4 py-2 text-left font-semibold text-slate-700">
                    {moduleLabel(module)}
                  </th>
                </tr>
                {modulePermissions.map((permission) => (
                  <tr key={permission.id}>
                    <td className="px-4 py-3 font-medium">
                      {permissionLabel(permission.code, permission.description)}
                      <details className="mt-1 text-xs font-normal text-slate-500">
                        <summary className="w-fit cursor-pointer">Technical permission code</summary>
                        <code>{permission.code}</code>
                      </details>
                    </td>
                    <td className="px-4 py-3">{moduleLabel(permission.module)}</td>
                  </tr>
                ))}
              </Fragment>
            ))}
            {permissions.length === 0 && <tr><td colSpan={2} className="px-4 py-8 text-center text-slate-500">{loadFailed ? 'Permissions could not be loaded.' : 'No permissions have been seeded yet.'}</td></tr>}
          </tbody>
        </table>
      </div>
    </ProtectedPage>
  );
}
