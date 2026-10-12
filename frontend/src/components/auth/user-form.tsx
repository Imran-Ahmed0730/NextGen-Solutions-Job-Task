'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { apiRequest } from '@/lib/auth-api';
import { userSchema } from '@/lib/auth-validation';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';

type RoleOption = { id: number; name: string; is_active: boolean };
type UserRecord = {
  id: number;
  username: string;
  full_name: string;
  email: string | null;
  mobile: string | null;
  is_active: boolean;
  roles: string[];
};

export function UserForm({ userId }: { userId: number | null }) {
  const router = useRouter();
  const [record, setRecord] = useState<UserRecord | null>(null);
  const [roles, setRoles] = useState<RoleOption[]>([]);
  const [selectedRoleIds, setSelectedRoleIds] = useState<number[]>([]);
  const [loadFailed, setLoadFailed] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([
      apiRequest<RoleOption[]>('/api/v1/auth/roles'),
      userId ? apiRequest<UserRecord>(`/api/v1/auth/users/${userId}`) : Promise.resolve(null),
    ])
      .then(([availableRoles, user]) => {
        setRoles(availableRoles.filter((role) => role.is_active));
        if (user) {
          setRecord(user);
          setSelectedRoleIds(
            availableRoles.filter((role) => user.roles.includes(role.name)).map((role) => role.id),
          );
        }
      })
      .catch((cause: unknown) => {
        setLoadFailed(true);
        showErrorToast(cause instanceof Error ? cause.message : 'Could not load user data');
      });
  }, [userId]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    const parsed = userSchema.safeParse({
      ...values,
      email: String(values.email ?? ''),
      mobile: String(values.mobile ?? ''),
      role_ids: selectedRoleIds,
    });
    if (!parsed.success) {
      showErrorToast(parsed.error.issues[0]?.message ?? 'Check the user details');
      return;
    }
    if (!userId && !parsed.data.password) {
      showErrorToast('Set an initial password for this user');
      return;
    }
    if (parsed.data.password && parsed.data.password.length < 8) {
      showErrorToast('Use at least 8 characters for the password');
      return;
    }

    const payload = {
      username: parsed.data.username,
      full_name: parsed.data.full_name,
      email: parsed.data.email || null,
      mobile: parsed.data.mobile || null,
      role_ids: parsed.data.role_ids,
      ...(userId ? {} : { password: parsed.data.password }),
    };
    setBusy(true);
    try {
      await apiRequest(
        userId ? `/api/v1/auth/users/${userId}` : '/api/v1/auth/users',
        { method: userId ? 'PATCH' : 'POST', body: JSON.stringify(payload) },
      );
      showSuccessToast(userId ? 'User updated.' : 'User created.');
      router.push('/users');
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not save user');
    } finally {
      setBusy(false);
    }
  }

  return (
    <ProtectedPage>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{userId ? 'Edit User' : 'Add User'}</h1>
          <p className="mt-1 text-sm text-slate-600">Assign roles to control this user’s access.</p>
        </div>
        <Link href="/users" className="text-sm text-emerald-800 underline">Back to users</Link>
      </div>
      {userId && !record && !loadFailed ? (
        <p className="mt-6 text-sm text-slate-500">Loading user…</p>
      ) : userId && loadFailed ? (
        <p className="mt-6 text-sm text-slate-600">User data could not be loaded.</p>
      ) : (
        <form key={record?.id ?? 'new'} className="mt-6 max-w-2xl space-y-4" onSubmit={submit}>
          <label className="block text-sm font-medium">
            Username
            <input
              name="username"
              defaultValue={record?.username}
              required
              readOnly={Boolean(userId)}
              className="mt-1 w-full rounded-md border px-3 py-2 read-only:bg-slate-50"
            />
          </label>
          <label className="block text-sm font-medium">
            Full name
            <input name="full_name" defaultValue={record?.full_name} required className="mt-1 w-full rounded-md border px-3 py-2" />
          </label>
          <label className="block text-sm font-medium">
            Email
            <input name="email" type="email" defaultValue={record?.email ?? ''} className="mt-1 w-full rounded-md border px-3 py-2" />
          </label>
          <label className="block text-sm font-medium">
            Mobile
            <input name="mobile" defaultValue={record?.mobile ?? ''} className="mt-1 w-full rounded-md border px-3 py-2" />
          </label>
          {!userId && (
            <label className="block text-sm font-medium">
              Initial password
              <input name="password" type="password" autoComplete="new-password" required className="mt-1 w-full rounded-md border px-3 py-2" />
            </label>
          )}
          <fieldset className="rounded-lg border border-slate-200 p-4">
            <legend className="px-1 text-sm font-medium">Roles</legend>
            {roles.length === 0 ? (
              <p className="text-sm text-slate-500">No active roles available.</p>
            ) : (
              <div className="grid gap-2 sm:grid-cols-2">
                {roles.map((role) => (
                  <label key={role.id} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={selectedRoleIds.includes(role.id)}
                      onChange={(event) =>
                        setSelectedRoleIds((current) =>
                          event.target.checked
                            ? [...current, role.id]
                            : current.filter((id) => id !== role.id),
                        )
                      }
                    />
                    {role.name}
                  </label>
                ))}
              </div>
            )}
          </fieldset>
          {userId && <p className="text-sm text-slate-600">Account status: {record?.is_active ? 'Active' : 'Inactive'}</p>}
          <button disabled={busy} className="rounded-md bg-emerald-700 px-4 py-2 font-medium text-white disabled:opacity-60">
            {busy ? 'Saving…' : 'Save user'}
          </button>
        </form>
      )}
    </ProtectedPage>
  );
}
