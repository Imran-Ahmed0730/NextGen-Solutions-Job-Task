'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { useSessionProfile } from '@/components/auth/session-shell';
import { apiRequest } from '@/lib/auth-api';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';
import { ActionIcon, IconActionButton } from '@/components/ui/action-icon';

type UserRecord = {
  id: number;
  username: string;
  full_name: string;
  email: string | null;
  is_active: boolean;
  roles: string[];
};

function UsersContent() {
  const profile = useSessionProfile();
  const [users, setUsers] = useState<UserRecord[]>([]);

  async function loadUsers() {
    try {
      setUsers(await apiRequest<UserRecord[]>('/api/v1/auth/users'));
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not load users');
    }
  }

  useEffect(() => {
    void loadUsers();
  }, []);

  async function setActive(userId: number, active: boolean) {
    try {
      await apiRequest(`/api/v1/auth/users/${userId}/${active ? 'activate' : 'deactivate'}`, {
        method: 'POST',
      });
      showSuccessToast(active ? 'User activated.' : 'User deactivated.');
      await loadUsers();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not update account status');
    }
  }

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Users</h1>
          <p className="mt-1 text-sm text-slate-600">Manage user accounts and roles.</p>
        </div>
        {profile?.permissions.includes('auth.users.create') && (
          <Link href="/users/new" className="inline-flex items-center gap-2 rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white">
            <ActionIcon name="add" />
            Add user
          </Link>
        )}
      </div>
      <div className="mt-6 overflow-x-auto rounded-lg border border-slate-200">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr><th className="px-4 py-3">User</th><th className="px-4 py-3">Roles</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Actions</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {users.map((user) => (
              <tr key={user.id}>
                <td className="px-4 py-3">
                  {profile?.permissions.includes('auth.users.update') ? (
                    <Link href={`/users/${user.id}`} className="font-medium text-emerald-800 underline">{user.full_name}</Link>
                  ) : (
                    <span className="font-medium">{user.full_name}</span>
                  )}
                  <p className="text-xs text-slate-500">{user.username}{user.email ? ` · ${user.email}` : ''}</p>
                </td>
                <td className="px-4 py-3">{user.roles.join(', ') || 'None'}</td>
                <td className="px-4 py-3">{user.is_active ? 'Active' : 'Inactive'}</td>
                <td className="px-4 py-3">
                  {profile?.permissions.includes('auth.users.update') && (
                    <Link
                      href={`/users/${user.id}`}
                      title={`Edit ${user.full_name}`}
                      aria-label={`Edit ${user.full_name}`}
                      className="mr-1 inline-flex rounded-lg p-2 text-emerald-800 hover:bg-emerald-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
                    >
                      <ActionIcon name="edit" />
                    </Link>
                  )}
                  {profile?.permissions.includes(user.is_active ? 'auth.users.delete' : 'auth.users.update') && (
                    <IconActionButton
                      icon={user.is_active ? 'deactivate' : 'activate'}
                      label={`${user.is_active ? 'Deactivate' : 'Activate'} ${user.full_name}`}
                      onClick={() => void setActive(user.id, !user.is_active)}
                      className={user.is_active ? 'p-2 text-rose-700 hover:bg-rose-50' : 'p-2 text-emerald-800 hover:bg-emerald-50'}
                    />
                  )}
                </td>
              </tr>
            ))}
            {users.length === 0 && <tr><td colSpan={4} className="px-4 py-8 text-center text-slate-500">No users found.</td></tr>}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default function UsersPage() {
  return (
    <ProtectedPage>
      <UsersContent />
    </ProtectedPage>
  );
}
