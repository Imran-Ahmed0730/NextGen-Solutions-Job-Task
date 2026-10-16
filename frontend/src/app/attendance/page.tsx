'use client';

import { useCallback, useEffect, useState, type ChangeEvent, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { useSessionProfile } from '@/components/auth/session-shell';
import { FieldError, getFieldErrors, RequiredMark, type FieldErrors } from '@/components/forms/field-error';
import { SearchableSelect } from '@/components/forms/searchable-select';
import { IconActionButton } from '@/components/ui/action-icon';
import { apiRequest } from '@/lib/auth-api';
import { statusLabel } from '@/lib/display-labels';
import {
  attendanceCreateSchema,
  attendanceDateRangeSchema,
  attendanceUpdateSchema,
} from '@/lib/auth-validation';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';

const workbookMime = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

type EmployeeOption = { id: number; code: string; name: string };
type AttendanceStatus = 'PRESENT' | 'ABSENT' | 'LEAVE' | 'LATE';
type AttendanceRecord = {
  id: number;
  employee_id: number;
  employee: EmployeeOption;
  att_date: string;
  status: AttendanceStatus;
  in_time: string | null;
  out_time: string | null;
};
type ImportResult = {
  created: number;
  rejected: number;
  errors: { row_number: number; message: string }[];
};
function todayLocalDate(): string {
  const today = new Date();
  return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(
    today.getDate(),
  ).padStart(2, '0')}`;
}

function downloadWorkbook(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function AttendanceContent() {
  const permissions = useSessionProfile()?.permissions ?? [];
  const canRead = permissions.includes('employees.attendance.read');
  const canCreate = permissions.includes('employees.attendance.create');
  const canUpdate = permissions.includes('employees.attendance.update');
  const today = todayLocalDate();
  const [employees, setEmployees] = useState<EmployeeOption[]>([]);
  const [records, setRecords] = useState<AttendanceRecord[]>([]);
  const [fromDate, setFromDate] = useState(today);
  const [toDate, setToDate] = useState(today);
  const [attDate, setAttDate] = useState(today);
  const [employeeId, setEmployeeId] = useState('');
  const [status, setStatus] = useState<AttendanceStatus>('PRESENT');
  const [inTime, setInTime] = useState('');
  const [outTime, setOutTime] = useState('');
  const [selected, setSelected] = useState<AttendanceRecord | null>(null);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [error, setError] = useState('');
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    const parsedRange = attendanceDateRangeSchema.safeParse({
      from_date: fromDate,
      to_date: toDate,
    });
    if (!parsedRange.success) {
      setError(parsedRange.error.issues[0]?.message ?? 'Enter a valid date range');
      return;
    }
    const query = new URLSearchParams(parsedRange.data);
    const [employeeOptions, attendance] = await Promise.all([
      apiRequest<EmployeeOption[]>('/api/v1/attendance/options'),
      apiRequest<AttendanceRecord[]>(`/api/v1/attendance?${query}`),
    ]);
    setEmployees(employeeOptions);
    setRecords(attendance);
    setError('');
  }, [fromDate, toDate]);

  useEffect(() => {
    if (!canRead) return;
    void reload().catch((cause: unknown) =>
      showErrorToast(cause instanceof Error ? cause.message : 'Could not load attendance'),
    );
  }, [canRead, reload]);

  function resetForm() {
    setSelected(null);
    setAttDate(todayLocalDate());
    setEmployeeId('');
    setStatus('PRESENT');
    setInTime('');
    setOutTime('');
    setErrors({});
  }

  function editRecord(record: AttendanceRecord) {
    setSelected(record);
    setAttDate(record.att_date);
    setEmployeeId(String(record.employee_id));
    setStatus(record.status);
    setInTime(record.in_time?.slice(0, 5) ?? '');
    setOutTime(record.out_time?.slice(0, 5) ?? '');
    setErrors({});
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payload = selected
      ? attendanceUpdateSchema.safeParse({
          status,
          in_time: inTime,
          out_time: outTime,
        })
      : attendanceCreateSchema.safeParse({
          employee_id: Number(employeeId),
          att_date: attDate,
          status,
          in_time: inTime,
          out_time: outTime,
        });
    if (!payload.success) {
      setErrors(getFieldErrors(payload.error.issues));
      return;
    }

    setErrors({});
    setBusy(true);
    try {
      await apiRequest<AttendanceRecord>(
        selected ? `/api/v1/attendance/${selected.id}` : '/api/v1/attendance',
        {
          method: selected ? 'PATCH' : 'POST',
          body: JSON.stringify(payload.data),
        },
      );
      showSuccessToast(selected ? 'Attendance updated.' : 'Attendance recorded.');
      setSelected(null);
      setEmployeeId('');
      setStatus('PRESENT');
      setInTime('');
      setOutTime('');
      await reload();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not save attendance');
    } finally {
      setBusy(false);
    }
  }

  async function importWorkbook(event: ChangeEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = '';
    if (!file) return;
    setBusy(true);
    setImportResult(null);
    try {
      if (!file.name.toLowerCase().endsWith('.xlsx')) {
        throw new Error('Choose an .xlsx attendance workbook.');
      }
      if (file.size > 5 * 1024 * 1024) {
        throw new Error('Workbook exceeds the 5 MB size limit.');
      }
      const result = await apiRequest<ImportResult>('/api/v1/attendance/import', {
        method: 'POST',
        headers: { 'Content-Type': workbookMime },
        body: file,
      });
      setImportResult(result);
      showSuccessToast(
        `Imported ${result.created} attendance row(s); ${result.rejected} row(s) need review.`,
      );
      await reload();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not import attendance workbook');
    } finally {
      setBusy(false);
    }
  }

  async function exportWorkbook(templateOnly = false) {
    const parsedRange = attendanceDateRangeSchema.safeParse({
      from_date: fromDate,
      to_date: toDate,
    });
    if (!parsedRange.success) {
      setError(parsedRange.error.issues[0]?.message ?? 'Enter a valid date range');
      return;
    }
    setBusy(true);
    try {
      const query = new URLSearchParams(parsedRange.data);
      const path = templateOnly
        ? '/api/v1/attendance/template'
        : `/api/v1/attendance/export?${query}`;
      const blob = await apiRequest<Blob>(path, {}, { responseType: 'blob' });
      const filename = templateOnly
        ? 'attendance_template.xlsx'
        : `attendance_${parsedRange.data.from_date}_to_${parsedRange.data.to_date}.xlsx`;
      downloadWorkbook(blob, filename);
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not export attendance');
    } finally {
      setBusy(false);
    }
  }

  if (!canRead) {
    return (
      <section className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
        Your account does not have permission to view employee attendance.
      </section>
    );
  }

  return (
    <main className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Attendance</h1>
        <p className="mt-1 text-sm text-slate-600">
          Record and update daily attendance, or use an Excel workbook for bulk entry.
        </p>
      </header>

      <section className="flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 bg-white p-4">
        <label className="text-sm font-medium text-slate-700">
          From date
          <input
            type="date"
            value={fromDate}
            onChange={(event) => setFromDate(event.target.value)}
            className="mt-1 block rounded-md border border-slate-300 px-3 py-2"
          />
        </label>
        <label className="text-sm font-medium text-slate-700">
          To date
          <input
            type="date"
            value={toDate}
            onChange={(event) => setToDate(event.target.value)}
            className="mt-1 block rounded-md border border-slate-300 px-3 py-2"
          />
        </label>
        <button
          type="button"
          disabled={busy}
          onClick={() => void exportWorkbook()}
          className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium disabled:opacity-60"
        >
          Export Excel
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void exportWorkbook(true)}
          className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium disabled:opacity-60"
        >
          Download template
        </button>
        {canCreate && (
          <label className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white">
            Import Excel
            <input
              type="file"
              accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              disabled={busy}
              onChange={(event) => void importWorkbook(event)}
              className="sr-only"
            />
          </label>
        )}
      </section>

      {error && <p role="alert" className="text-sm text-rose-700">{error}</p>}
      {importResult && (
        <section role="status" className="space-y-2 rounded-lg border border-slate-200 bg-white p-4">
          <p>
            Import complete: {importResult.created} created, {importResult.rejected} rejected.
          </p>
          {importResult.errors.length > 0 && (
            <ul className="list-inside list-disc text-sm text-rose-700">
              {importResult.errors.map((item) => (
                <li key={`${item.row_number}-${item.message}`}>
                  Row {item.row_number}: {item.message}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {(canCreate || (selected && canUpdate)) && (
        <form
          noValidate
          onSubmit={(event) => void submit(event)}
          className="grid gap-4 rounded-lg border border-slate-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-3"
        >
          <h2 className="text-lg font-medium sm:col-span-2 lg:col-span-3">
            {selected ? 'Edit attendance' : 'Record attendance'}
          </h2>
          <label className="text-sm font-medium text-slate-700">
            Employee<RequiredMark />
            <SearchableSelect
              aria-label="Employee"
              required
              disabled={Boolean(selected)}
              placeholder="Search or select an employee"
              value={employeeId}
              onChange={setEmployeeId}
              options={employees.map((employee) => ({
                value: String(employee.id),
                label: `${employee.code} - ${employee.name}`,
              }))}
            />
            <FieldError id="attendance-employee-error" message={errors.employee_id} />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Attendance date<RequiredMark />
            <input
              type="date"
              required
              disabled={Boolean(selected)}
              value={attDate}
              onChange={(event) => setAttDate(event.target.value)}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            />
            <FieldError id="attendance-date-error" message={errors.att_date} />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Status<RequiredMark />
            <select
              required
              value={status}
              onChange={(event) => setStatus(event.target.value as AttendanceStatus)}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            >
              <option value="PRESENT">Present</option>
              <option value="ABSENT">Absent</option>
              <option value="LEAVE">Leave</option>
              <option value="LATE">Late</option>
            </select>
            <FieldError id="attendance-status-error" message={errors.status} />
          </label>
          <label className="text-sm font-medium text-slate-700">
            In time
            <input
              type="time"
              value={inTime}
              onChange={(event) => setInTime(event.target.value)}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            />
            <FieldError id="attendance-in-time-error" message={errors.in_time} />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Out time
            <input
              type="time"
              value={outTime}
              onChange={(event) => setOutTime(event.target.value)}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            />
            <FieldError id="attendance-out-time-error" message={errors.out_time} />
          </label>
          <div className="flex items-end gap-2">
            <button
              type="submit"
              disabled={busy}
              className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {busy ? 'Saving…' : selected ? 'Save attendance' : 'Record attendance'}
            </button>
            {selected && (
              <button
                type="button"
                onClick={resetForm}
                className="rounded-md border border-slate-300 px-4 py-2 text-sm"
              >
                Cancel
              </button>
            )}
          </div>
        </form>
      )}

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-600">
            <tr>
              <th className="px-4 py-3">Date</th>
              <th className="px-4 py-3">Employee</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">In time</th>
              <th className="px-4 py-3">Out time</th>
              {canUpdate && <th className="px-4 py-3">Actions</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {records.map((record) => (
              <tr key={record.id}>
                <td className="px-4 py-3">{record.att_date}</td>
                <td className="px-4 py-3">
                  <span className="font-medium">{record.employee.name}</span>
                  <span className="ml-2 text-xs text-slate-500">{record.employee.code}</span>
                </td>
                <td className="px-4 py-3">{statusLabel(record.status)}</td>
                <td className="px-4 py-3">{record.in_time?.slice(0, 5) ?? '—'}</td>
                <td className="px-4 py-3">{record.out_time?.slice(0, 5) ?? '—'}</td>
                {canUpdate && (
                  <td className="px-4 py-3">
                    <IconActionButton
                      icon="edit"
                      label="Edit attendance"
                      tooltip={`Edit attendance for ${record.employee.name}`}
                      onClick={() => editRecord(record)}
                      className="p-2 text-emerald-800 hover:bg-emerald-50"
                    />
                  </td>
                )}
              </tr>
            ))}
            {records.length === 0 && (
              <tr>
                <td colSpan={canUpdate ? 6 : 5} className="px-4 py-5 text-slate-600">
                  No attendance records found for this date range.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </main>
  );
}

export default function AttendancePage() {
  return (
    <ProtectedPage>
      <AttendanceContent />
    </ProtectedPage>
  );
}
