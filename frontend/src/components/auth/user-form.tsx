'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
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
import { ActionIcon } from '@/components/ui/action-icon';
import { apiRequest } from '@/lib/auth-api';
import { userSchema } from '@/lib/auth-validation';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';

type RoleOption = { id: number; name: string; is_active: boolean };
type EmployeeOption = { id: number; code: string; name: string };
type UserRecord = {
  id: number;
  username: string;
  full_name: string;
  email: string | null;
  mobile: string | null;
  employee_id: number | null;
  is_active: boolean;
  roles: string[];
};

export function UserForm({ userId }: { userId: number | null }) {
  const router = useRouter();
  const profile = useSessionProfile();
  const canReadEmployees = profile?.permissions.includes('employees.read') ?? false;
  const [record, setRecord] = useState<UserRecord | null>(null);
  const [roles, setRoles] = useState<RoleOption[]>([]);
  const [employees, setEmployees] = useState<EmployeeOption[]>([]);
  const [selectedRoleIds, setSelectedRoleIds] = useState<number[]>([]);
  const [loadFailed, setLoadFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});

  useEffect(() => {
    Promise.all([
      apiRequest<RoleOption[]>('/api/v1/auth/roles'),
      userId ? apiRequest<UserRecord>(`/api/v1/auth/users/${userId}`) : Promise.resolve(null),
      canReadEmployees
        ? apiRequest<EmployeeOption[]>('/api/v1/employees?limit=200')
        : Promise.resolve([]),
    ])
      .then(([availableRoles, user, availableEmployees]) => {
        setRoles(availableRoles.filter((role) => role.is_active));
        setEmployees(availableEmployees);
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
  }, [canReadEmployees, userId]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    const parsed = userSchema.safeParse({
      ...values,
      email: String(values.email ?? ''),
      mobile: String(values.mobile ?? ''),
      employee_id: values.employee_id ? Number(values.employee_id) : null,
      role_ids: selectedRoleIds,
    });
    if (!parsed.success) {
      setErrors(getFieldErrors(parsed.error.issues));
      return;
    }
    if (!userId && !parsed.data.password) {
      setErrors({ password: 'Set an initial password for this user' });
      return;
    }
    if (parsed.data.password && parsed.data.password.length < 8) {
      setErrors({ password: 'Use at least 8 characters for the password' });
      return;
    }

    setErrors({});
    const payload = {
      username: parsed.data.username,
      full_name: parsed.data.full_name,
      email: parsed.data.email || null,
      mobile: parsed.data.mobile || null,
      role_ids: parsed.data.role_ids,
      ...(canReadEmployees ? { employee_id: parsed.data.employee_id ?? null } : {}),
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
      const apiErrors = getApiFieldErrors(cause);
      if (Object.keys(apiErrors).length) setErrors(apiErrors);
      else showErrorToast(cause instanceof Error ? cause.message : 'Could not save user');
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
        <form key={record?.id ?? 'new'} noValidate className="mt-6 max-w-2xl space-y-4" onSubmit={submit}>
          <label className="block text-sm font-medium">
            Username<RequiredMark />
            <input type="text"
              name="username"
              placeholder="Choose a username"
              defaultValue={record?.username}
              minLength={1}
              maxLength={100}
              pattern="[A-Za-z0-9][A-Za-z0-9._-]*"
              title="Use letters, numbers, dots, underscores, or hyphens"
              required
              readOnly={Boolean(userId)}
              aria-invalid={Boolean(errors.username)}
              aria-describedby={errors.username ? 'username-error' : undefined}
              className="mt-1 w-full rounded-md border px-3 py-2 read-only:bg-slate-50"
            />
            <FieldError id="username-error" message={errors.username} />
          </label>
          <label className="block text-sm font-medium">
            Full name<RequiredMark />
            <input type="text" name="full_name" placeholder="Enter the user's full name" defaultValue={record?.full_name} minLength={1} maxLength={255} required aria-invalid={Boolean(errors.full_name)} aria-describedby={errors.full_name ? 'full-name-error' : undefined} className="mt-1 w-full rounded-md border px-3 py-2" />
            <FieldError id="full-name-error" message={errors.full_name} />
          </label>
          <label className="block text-sm font-medium">
            Email
            <input name="email" type="email" placeholder="name@example.com" maxLength={255} defaultValue={record?.email ?? ''} aria-invalid={Boolean(errors.email)} aria-describedby={errors.email ? 'user-email-error' : undefined} className="mt-1 w-full rounded-md border px-3 py-2" />
            <FieldError id="user-email-error" message={errors.email} />
          </label>
          <label className="block text-sm font-medium">
            Mobile
            <input name="mobile" type="tel" inputMode="numeric" pattern="01[3-9][0-9]{8}" maxLength={11} placeholder="e.g. 01712345678" defaultValue={record?.mobile ?? ''} aria-invalid={Boolean(errors.mobile)} aria-describedby={errors.mobile ? 'user-mobile-error' : undefined} className="mt-1 w-full rounded-md border px-3 py-2" />
            <FieldError id="user-mobile-error" message={errors.mobile} />
          </label>
          {canReadEmployees && (
            <label className="block text-sm font-medium">
              Linked employee
              <select
                name="employee_id"
                defaultValue={record?.employee_id?.toString() ?? ''}
                className="mt-1 w-full rounded-md border px-3 py-2"
              >
                <option value="">No employee linked</option>
                {record?.employee_id &&
                  !employees.some((employee) => employee.id === record.employee_id) && (
                    <option value={record.employee_id}>
                      Employee #{record.employee_id} (currently linked)
                    </option>
                  )}
                {employees.map((employee) => (
                  <option key={employee.id} value={employee.id}>
                    {employee.code} — {employee.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          {!userId && (
            <label className="block text-sm font-medium">
              Initial password<RequiredMark />
              <input name="password" type="password" placeholder="At least 8 characters" autoComplete="new-password" minLength={8} maxLength={256} required aria-invalid={Boolean(errors.password)} aria-describedby={errors.password ? 'user-password-error' : undefined} className="mt-1 w-full rounded-md border px-3 py-2" />
              <FieldError id="user-password-error" message={errors.password} />
            </label>
          )}
          <fieldset
            className="rounded-lg border border-slate-200 p-4"
            aria-invalid={Boolean(errors.role_ids)}
            aria-describedby={errors.role_ids ? 'user-roles-error' : undefined}
          >
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
          <FieldError id="user-roles-error" message={errors.role_ids} />
          {userId && <p className="text-sm text-slate-600">Account status: {record?.is_active ? 'Active' : 'Inactive'}</p>}
          <button disabled={busy} className="inline-flex items-center gap-2 rounded-md bg-emerald-700 px-4 py-2 font-medium text-white disabled:opacity-60">
            <ActionIcon name="save" />
            {busy ? 'Saving…' : 'Save user'}
          </button>
        </form>
      )}
    </ProtectedPage>
  );
}
