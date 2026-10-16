'use client';

import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import Swal from 'sweetalert2';

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
import { employeeSchema } from '@/lib/auth-validation';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';

type EmployeeRecord = {
  id: number;
  code: string;
  name: string;
  mobile: string | null;
  email: string | null;
  designation: string | null;
  department: string | null;
  join_date: string;
  base_salary: string;
  is_active: boolean;
  deleted_at: string | null;
};

function EmployeesContent() {
  const profile = useSessionProfile();
  const [employees, setEmployees] = useState<EmployeeRecord[]>([]);
  const [selected, setSelected] = useState<EmployeeRecord | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [includeInactive, setIncludeInactive] = useState(false);
  const [search, setSearch] = useState('');
  const [errors, setErrors] = useState<FieldErrors>({});
  const listRequestId = useRef(0);

  const reload = useCallback(async () => {
    const requestId = ++listRequestId.current;
    const params = new URLSearchParams();
    if (includeInactive) params.set('include_inactive', 'true');
    if (search.trim()) params.set('search', search.trim());
    const query = params.size ? `?${params.toString()}` : '';
    const result = await apiRequest<EmployeeRecord[]>(`/api/v1/employees${query}`, {
      cache: 'no-store',
    });
    if (requestId === listRequestId.current) setEmployees(result);
  }, [includeInactive, search]);

  useEffect(() => {
    void reload().catch((cause: unknown) =>
      showErrorToast(cause instanceof Error ? cause.message : 'Could not load employees'),
    );
  }, [reload]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const parsed = employeeSchema.safeParse({
      code: form.get('code'),
      name: form.get('name'),
      mobile: form.get('mobile'),
      email: form.get('email') || null,
      designation: form.get('designation'),
      department: form.get('department'),
      join_date: form.get('join_date'),
      base_salary: form.get('base_salary'),
    });
    if (!parsed.success) {
      setErrors(getFieldErrors(parsed.error.issues));
      return;
    }
    setErrors({});
    try {
      await apiRequest<EmployeeRecord>(
        selected ? `/api/v1/employees/${selected.id}` : '/api/v1/employees',
        {
          method: selected ? 'PATCH' : 'POST',
          body: JSON.stringify(parsed.data),
        },
      );
    } catch (cause) {
      const apiErrors = getApiFieldErrors(cause);
      if (Object.keys(apiErrors).length) setErrors(apiErrors);
      else showErrorToast(cause instanceof Error ? cause.message : 'Could not save employee');
      return;
    }
    showSuccessToast(selected ? 'Employee updated.' : 'Employee created.');
    setSelected(null);
    setFormOpen(false);
    try {
      await reload();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not refresh employees');
    }
  }

  async function setDeleted(employee: EmployeeRecord, restore: boolean) {
    if (!restore) {
      const confirmation = await Swal.fire({
        title: 'Delete employee?',
        text: `Are you sure you want to delete "${employee.name}"? The record will be archived.`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#b91c1c',
        cancelButtonColor: '#64748b',
        confirmButtonText: 'Yes, delete',
      });
      if (!confirmation.isConfirmed) return;
    }
    try {
      await apiRequest<EmployeeRecord>(
        restore
          ? `/api/v1/employees/${employee.id}/restore`
          : `/api/v1/employees/${employee.id}`,
        { method: restore ? 'POST' : 'DELETE' },
      );
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not update employee');
      return;
    }
    showSuccessToast(restore ? 'Employee restored.' : 'Employee deleted.');
    try {
      await reload();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not refresh employees');
    }
  }

  return (
    <main className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Employees</h1>
          <p className="mt-1 text-sm text-slate-600">
            Maintain employee details and monthly base salary.
          </p>
        </div>
        {profile?.permissions.includes('employees.create') && !formOpen && (
          <button
            type="button"
            onClick={() => {
              setSelected(null);
              setErrors({});
              setFormOpen(true);
            }}
            className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white"
          >
            Add employee
          </button>
        )}
      </div>

      {formOpen && (
        <form
          key={selected?.id ?? 'new-employee'}
          noValidate
          onSubmit={submit}
          className="grid gap-4 rounded-lg border border-slate-200 p-4 sm:grid-cols-2 lg:grid-cols-3"
        >
          <h2 className="text-lg font-medium sm:col-span-2 lg:col-span-3">
            {selected ? 'Edit employee' : 'New employee'}
          </h2>
          <label className="text-sm font-medium">
            Employee code<RequiredMark />
            <input type="text"
              name="code"
              placeholder="e.g. EMP-001"
              defaultValue={selected?.code ?? ''}
              required
              aria-invalid={Boolean(errors.code)}
              aria-describedby={errors.code ? 'employee-code-error' : undefined}
              className="mt-1 w-full rounded-md border px-3 py-2"
            />
            <FieldError id="employee-code-error" message={errors.code} />
          </label>
          <label className="text-sm font-medium">
            Employee name<RequiredMark />
            <input type="text"
              name="name"
              placeholder="e.g. Ayesha Rahman"
              defaultValue={selected?.name ?? ''}
              required
              aria-invalid={Boolean(errors.name)}
              aria-describedby={errors.name ? 'employee-name-error' : undefined}
              className="mt-1 w-full rounded-md border px-3 py-2"
            />
            <FieldError id="employee-name-error" message={errors.name} />
          </label>
          <label className="text-sm font-medium">
            Mobile<RequiredMark />
            <input
              name="mobile"
              type="tel"
              inputMode="numeric"
              placeholder="e.g. 01712345678"
              defaultValue={selected?.mobile ?? ''}
              maxLength={11}
              required
              aria-invalid={Boolean(errors.mobile)}
              aria-describedby={errors.mobile ? 'employee-mobile-error' : undefined}
              className="mt-1 w-full rounded-md border px-3 py-2"
            />
            <FieldError id="employee-mobile-error" message={errors.mobile} />
          </label>
          <label className="text-sm font-medium">
            Email
            <input
              name="email"
              type="email"
              placeholder="e.g. employee@example.com"
              defaultValue={selected?.email ?? ''}
              maxLength={255}
              aria-invalid={Boolean(errors.email)}
              aria-describedby={errors.email ? 'employee-email-error' : undefined}
              className="mt-1 w-full rounded-md border px-3 py-2"
            />
            <FieldError id="employee-email-error" message={errors.email} />
          </label>
          <label className="text-sm font-medium">
            Designation
            <input type="text"
              name="designation"
              placeholder="e.g. Production supervisor"
              defaultValue={selected?.designation ?? ''}
              maxLength={100}
              className="mt-1 w-full rounded-md border px-3 py-2"
            />
          </label>
          <label className="text-sm font-medium">
            Department
            <input type="text"
              name="department"
              placeholder="e.g. Production"
              defaultValue={selected?.department ?? ''}
              maxLength={100}
              className="mt-1 w-full rounded-md border px-3 py-2"
            />
          </label>
          <label className="text-sm font-medium">
            Joining date<RequiredMark />
            <input
              name="join_date"
              type="date"
              defaultValue={selected?.join_date ?? ''}
              required
              aria-invalid={Boolean(errors.join_date)}
              aria-describedby={errors.join_date ? 'employee-join-date-error' : undefined}
              className="mt-1 w-full rounded-md border px-3 py-2"
            />
            <FieldError id="employee-join-date-error" message={errors.join_date} />
          </label>
          <label className="text-sm font-medium">
            Monthly base salary<RequiredMark />
            <input
              name="base_salary"
              type="number"
              min="0"
              step="0.01"
              placeholder="e.g. 25000.00"
              defaultValue={selected?.base_salary ?? ''}
              required
              aria-invalid={Boolean(errors.base_salary)}
              aria-describedby={errors.base_salary ? 'employee-salary-error' : undefined}
              className="mt-1 w-full rounded-md border px-3 py-2"
            />
            <FieldError id="employee-salary-error" message={errors.base_salary} />
          </label>
          <div className="flex gap-2 sm:col-span-2 lg:col-span-3">
            <button className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white">
              {selected ? 'Save employee' : 'Create employee'}
            </button>
            <button
              type="button"
              onClick={() => {
                setFormOpen(false);
                setSelected(null);
                setErrors({});
              }}
              className="rounded-md border px-4 py-2 text-sm"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      <div className="flex flex-wrap items-center gap-4">
        <label className="text-sm font-medium">
          Search employees
          <input
            type="search"
            placeholder="Name, code, email, or mobile"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className="mt-1 block w-72 max-w-full rounded-md border px-3 py-2"
          />
        </label>
        <label className="inline-flex items-center gap-2 text-sm text-slate-600">
          <input
            type="checkbox"
            checked={includeInactive}
            onChange={(event) => setIncludeInactive(event.target.checked)}
          />
          Show deleted employees
        </label>
      </div>

      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-4 py-3">Employee</th>
              <th className="px-4 py-3">Contact</th>
              <th className="px-4 py-3">Department / designation</th>
              <th className="px-4 py-3">Joined</th>
              <th className="px-4 py-3 text-right">Base salary</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {employees.map((employee) => (
              <tr key={employee.id}>
                <td className="px-4 py-3">
                  <p className="font-medium">{employee.name}</p>
                  <p className="font-mono text-xs text-slate-500">{employee.code}</p>
                </td>
                <td className="px-4 py-3">
                  <p>{employee.mobile ?? '—'}</p>
                  <p className="text-slate-500">{employee.email ?? '—'}</p>
                </td>
                <td className="px-4 py-3">
                  <p>{employee.department ?? '—'}</p>
                  <p className="text-slate-500">{employee.designation ?? '—'}</p>
                </td>
                <td className="px-4 py-3">{employee.join_date}</td>
                <td className="px-4 py-3 text-right tabular-nums">
                  {Number(employee.base_salary).toFixed(2)}
                </td>
                <td className="px-4 py-3">{employee.is_active ? 'Active' : 'Deleted'}</td>
                <td className="space-x-2 px-4 py-3">
                  {employee.is_active && profile?.permissions.includes('employees.update') && (
                    <button
                      type="button"
                      onClick={() => {
                        setErrors({});
                        setSelected(employee);
                        setFormOpen(true);
                      }}
                      className="text-emerald-800 underline"
                    >
                      Edit
                    </button>
                  )}
                  {employee.is_active && profile?.permissions.includes('employees.delete') && (
                    <button
                      type="button"
                      onClick={() => void setDeleted(employee, false)}
                      className="text-rose-700 underline"
                    >
                      Delete
                    </button>
                  )}
                  {!employee.is_active && profile?.permissions.includes('employees.update') && (
                    <button
                      type="button"
                      onClick={() => void setDeleted(employee, true)}
                      className="text-emerald-800 underline"
                    >
                      Restore
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {employees.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-slate-500">
                  No employees found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </main>
  );
}

export default function EmployeesPage() {
  return (
    <ProtectedPage>
      <EmployeesContent />
    </ProtectedPage>
  );
}
