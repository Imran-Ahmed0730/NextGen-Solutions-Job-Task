'use client';

import { useEffect, useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { useSessionProfile } from '@/components/auth/session-shell';
import { apiRequest } from '@/lib/auth-api';
import { roleSchema } from '@/lib/auth-validation';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';

type PermissionRecord = { id: number; code: string; module: string; description: string | null };
type RoleRecord = {
  id: number;
  name: string;
  description: string | null;
  is_active: boolean;
  permission_ids: number[];
  permission_codes: string[];
};

export default function RolesPage() {
  const profile = useSessionProfile();
  const [roles, setRoles] = useState<RoleRecord[]>([]);
  const [permissions, setPermissions] = useState<PermissionRecord[]>([]);
  const [selected, setSelected] = useState<RoleRecord | null>(null);

  async function load() {
    try {
      const [roleList, permissionList] = await Promise.all([
        apiRequest<RoleRecord[]>('/api/v1/auth/roles'),
        apiRequest<PermissionRecord[]>('/api/v1/auth/permissions'),
      ]);
      setRoles(roleList);
      setPermissions(permissionList);
      if (selected) setSelected(roleList.find((item) => item.id === selected.id) ?? null);
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not load roles');
    }
  }

  useEffect(() => {
    void load();
    // Data is loaded once on entry; the selection is refreshed by explicit actions.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const parsed = roleSchema.safeParse({
      name: form.get('name'),
      description: form.get('description') || '',
      permission_ids: form.getAll('permission_ids').map(Number),
    });
    if (!parsed.success) {
      showErrorToast(parsed.error.issues[0]?.message ?? 'Check the role details');
      return;
    }
    try {
      const result = await apiRequest<RoleRecord>(
        selected ? `/api/v1/auth/roles/${selected.id}` : '/api/v1/auth/roles',
        {
          method: selected ? 'PATCH' : 'POST',
          body: JSON.stringify(parsed.data),
        },
      );
      setSelected(result);
      showSuccessToast('Role saved.');
      await load();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not save role');
    }
  }

  async function deactivate() {
    if (!selected) return;
    try {
      await apiRequest(`/api/v1/auth/roles/${selected.id}/deactivate`, { method: 'POST' });
      showSuccessToast('Role deactivated.');
      setSelected(null);
      await load();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not deactivate role');
    }
  }

  async function activate() {
    if (!selected) return;
    try {
      await apiRequest(`/api/v1/auth/roles/${selected.id}/activate`, { method: 'POST' });
      showSuccessToast('Role activated.');
      await load();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not activate role');
    }
  }

  return (
    <ProtectedPage>
      <h1 className="text-2xl font-semibold">Roles</h1>
      <p className="mt-1 text-sm text-slate-600">Create roles and grant permissions from the catalog.</p>
      <div className="mt-6 grid gap-6 lg:grid-cols-[260px_1fr]">
        <section className="rounded-lg border border-slate-200 p-3">
          {profile?.permissions.includes('auth.roles.create') && (
            <button
              type="button"
              onClick={() => setSelected(null)}
              className="mb-2 w-full rounded-md border border-dashed border-slate-300 px-3 py-2 text-left text-sm hover:bg-slate-50"
            >
              + New role
            </button>
          )}
          <ul className="space-y-1">
            {roles.map((role) => (
              <li key={role.id}>
                <button
                  type="button"
                  onClick={() => setSelected(role)}
                  className={`w-full rounded-md px-3 py-2 text-left text-sm ${
                    selected?.id === role.id ? 'bg-emerald-50 text-emerald-900' : 'hover:bg-slate-50'
                  }`}
                >
                  {role.name}
                  <span className="ml-2 text-xs text-slate-500">{role.is_active ? 'Active' : 'Inactive'}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
        {(selected
          ? profile?.permissions.includes('auth.roles.update')
          : profile?.permissions.includes('auth.roles.create')) && (
        <form key={selected?.id ?? 'new-role'} className="space-y-4" onSubmit={submit}>
          <label className="block text-sm font-medium">
            Role name
            <input name="name" required defaultValue={selected?.name ?? ''} className="mt-1 w-full rounded-md border px-3 py-2" />
          </label>
          <label className="block text-sm font-medium">
            Description
            <textarea name="description" rows={2} defaultValue={selected?.description ?? ''} className="mt-1 w-full rounded-md border px-3 py-2" />
          </label>
          <fieldset className="rounded-lg border border-slate-200 p-4">
            <legend className="px-1 text-sm font-medium">Permissions</legend>
            <div className="grid gap-2 sm:grid-cols-2">
              {permissions.map((permission) => (
                <label key={permission.id} className="flex items-start gap-2 text-sm">
                  <input
                    type="checkbox"
                    name="permission_ids"
                    value={permission.id}
                    defaultChecked={selected?.permission_ids.includes(permission.id) ?? false}
                    className="mt-1"
                  />
                  <span>
                    <span className="font-medium">{permission.code}</span>
                    {permission.description && <span className="block text-xs text-slate-500">{permission.description}</span>}
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
          {selected && (
            <p className="text-sm text-slate-600">
              Status: {selected.is_active ? 'Active' : 'Inactive'}
              {selected.is_active && profile?.permissions.includes('auth.roles.delete') && (
                <button type="button" onClick={() => void deactivate()} className="ml-3 text-rose-700 underline">
                  Deactivate role
                </button>
              )}
              {!selected.is_active && profile?.permissions.includes('auth.roles.update') && (
                <button type="button" onClick={() => void activate()} className="ml-3 text-emerald-800 underline">
                  Activate role
                </button>
              )}
            </p>
          )}
          <button className="rounded-md bg-emerald-700 px-4 py-2 font-medium text-white">
            {selected ? 'Save role' : 'Create role'}
          </button>
        </form>
        )}
      </div>
    </ProtectedPage>
  );
}
