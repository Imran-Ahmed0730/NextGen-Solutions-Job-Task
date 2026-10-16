'use client';

import { useEffect, useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { useSessionProfile } from '@/components/auth/session-shell';
import {
  FieldError,
  getApiFieldErrors,
  getFieldErrors,
  RequiredMark,
  type FieldErrors,
} from '@/components/forms/field-error';
import { apiRequest } from '@/lib/auth-api';
import { roleSchema } from '@/lib/auth-validation';
import { moduleLabel, permissionLabel } from '@/lib/display-labels';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';
import { ActionIcon, IconActionButton } from '@/components/ui/action-icon';

type PermissionRecord = { id: number; code: string; module: string; description: string | null };
type RoleRecord = {
  id: number;
  name: string;
  description: string | null;
  is_active: boolean;
  permission_ids: number[];
  permission_codes: string[];
};

function RolesContent() {
  const profile = useSessionProfile();
  const [roles, setRoles] = useState<RoleRecord[]>([]);
  const [permissions, setPermissions] = useState<PermissionRecord[]>([]);
  const [selected, setSelected] = useState<RoleRecord | null>(null);
  const [errors, setErrors] = useState<FieldErrors>({});
  const permissionsByModule = permissions.reduce<Record<string, PermissionRecord[]>>(
    (groups, permission) => {
      (groups[permission.module] ??= []).push(permission);
      return groups;
    },
    {},
  );

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
      setErrors(getFieldErrors(parsed.error.issues));
      return;
    }
    setErrors({});
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
      const apiErrors = getApiFieldErrors(cause);
      if (Object.keys(apiErrors).length) setErrors(apiErrors);
      else showErrorToast(cause instanceof Error ? cause.message : 'Could not save role');
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
    <>
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
              <span className="inline-flex items-center gap-2">
                <ActionIcon name="add" />
                New role
              </span>
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
        <form key={selected?.id ?? 'new-role'} noValidate className="space-y-4" onSubmit={submit}>
          <label className="block text-sm font-medium">
            Role name<RequiredMark />
            <input type="text" name="name" placeholder="e.g. Store Manager" minLength={1} maxLength={100} required aria-invalid={Boolean(errors.name)} aria-describedby={errors.name ? 'role-name-error' : undefined} defaultValue={selected?.name ?? ''} className="mt-1 w-full rounded-md border px-3 py-2" />
            <FieldError id="role-name-error" message={errors.name} />
          </label>
          <label className="block text-sm font-medium">
            Description
            <textarea name="description" rows={2} maxLength={2000} placeholder="Describe this role's responsibilities (optional)" defaultValue={selected?.description ?? ''} className="mt-1 w-full rounded-md border px-3 py-2" />
          </label>
          <fieldset
            className="rounded-lg border border-slate-200 p-4"
            aria-invalid={Boolean(errors.permission_ids)}
            aria-describedby={errors.permission_ids ? 'role-permissions-error' : undefined}
          >
            <legend className="px-1 text-sm font-medium">Permissions by work area</legend>
            <p className="mb-4 text-xs text-slate-500">
              Select the tasks this role is allowed to perform.
            </p>
            <div className="space-y-5">
              {Object.entries(permissionsByModule).map(([module, modulePermissions]) => (
                <section key={module}>
                  <h3 className="mb-2 text-sm font-semibold text-slate-800">
                    {moduleLabel(module)}
                  </h3>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {modulePermissions.map((permission) => (
                      <label key={permission.id} className="flex items-start gap-2 text-sm">
                        <input
                          type="checkbox"
                          name="permission_ids"
                          value={permission.id}
                          defaultChecked={selected?.permission_ids.includes(permission.id) ?? false}
                          className="mt-1"
                        />
                        <span className="min-w-0">
                          <span className="block font-medium">
                            {permissionLabel(permission.code, permission.description)}
                          </span>
                          <details className="mt-0.5 text-xs text-slate-500">
                            <summary className="w-fit cursor-pointer">Technical permission code</summary>
                            <code>{permission.code}</code>
                          </details>
                        </span>
                      </label>
                    ))}
                  </div>
                </section>
              ))}
            </div>
          </fieldset>
          <FieldError id="role-permissions-error" message={errors.permission_ids} />
          {selected && (
            <p className="text-sm text-slate-600">
              Status: {selected.is_active ? 'Active' : 'Inactive'}
              {selected.is_active && profile?.permissions.includes('auth.roles.delete') && (
                <IconActionButton
                  icon="deactivate"
                  label="Deactivate role"
                  onClick={() => void deactivate()}
                  className="ml-3 p-2 text-rose-700 hover:bg-rose-50"
                />
              )}
              {!selected.is_active && profile?.permissions.includes('auth.roles.update') && (
                <IconActionButton
                  icon="activate"
                  label="Activate role"
                  onClick={() => void activate()}
                  className="ml-3 p-2 text-emerald-800 hover:bg-emerald-50"
                />
              )}
            </p>
          )}
          <div className="flex gap-3">
            <button className="inline-flex items-center gap-2 rounded-md bg-emerald-700 px-4 py-2 font-medium text-white">
              <ActionIcon name="save" />
              {selected ? 'Save role' : 'Create role'}
            </button>
            {selected && (
              <button
                type="button"
                onClick={() => setSelected(null)}
                className="rounded-md border border-slate-300 px-4 py-2 text-sm"
              >
                Cancel
              </button>
            )}
          </div>
        </form>
        )}
      </div>
    </>
  );
}

export default function RolesPage() {
  return (
    <ProtectedPage>
      <RolesContent />
    </ProtectedPage>
  );
}
