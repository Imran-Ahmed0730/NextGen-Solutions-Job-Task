import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  apiRequest: vi.fn(),
  showErrorToast: vi.fn(),
  showSuccessToast: vi.fn(),
}));

vi.mock('@/components/auth/protected-page', () => ({
  ProtectedPage: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock('@/components/auth/session-shell', () => ({
  useSessionProfile: () => ({
    permissions: [
      'employees.attendance.read',
      'employees.attendance.create',
      'employees.attendance.update',
    ],
  }),
}));

vi.mock('@/lib/auth-api', () => ({
  apiRequest: mocks.apiRequest,
}));

vi.mock('@/lib/notifications', () => ({
  showErrorToast: mocks.showErrorToast,
  showSuccessToast: mocks.showSuccessToast,
}));

import AttendancePage from './page';

describe('AttendancePage', () => {
  beforeEach(() => {
    mocks.apiRequest.mockReset();
    mocks.showErrorToast.mockReset();
    mocks.showSuccessToast.mockReset();
    let records: Record<string, unknown>[] = [];
    mocks.apiRequest.mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/v1/attendance/options') {
        return Promise.resolve([{ id: 1, code: 'EMP-001', name: 'Ayesha Rahman' }]);
      }
      if (path.startsWith('/api/v1/attendance?')) return Promise.resolve(records);
      if (path === '/api/v1/attendance/import') {
        return Promise.resolve({
          created: 1,
          rejected: 1,
          errors: [{ row_number: 3, message: 'Employee code not found' }],
        });
      }
      if (
        path === '/api/v1/attendance/template' ||
        path.startsWith('/api/v1/attendance/export?')
      ) {
        return Promise.resolve(new Blob(['workbook']));
      }
      if (path === '/api/v1/attendance' && init?.method === 'POST') {
        const body = JSON.parse(String(init.body)) as Record<string, unknown>;
        const record = {
          id: 4,
          employee_id: 1,
          employee: { id: 1, code: 'EMP-001', name: 'Ayesha Rahman' },
          ...body,
        };
        records = [record];
        return Promise.resolve(record);
      }
      if (path === '/api/v1/attendance/4' && init?.method === 'PATCH') {
        const body = JSON.parse(String(init.body)) as Record<string, unknown>;
        records = records.map((record) => ({ ...record, ...body }));
        return Promise.resolve(records[0]);
      }
      return Promise.resolve([]);
    });
  });

  it('records and edits an employee attendance row', async () => {
    render(<AttendancePage />);
    await screen.findByRole('heading', { name: 'Attendance' });

    fireEvent.focus(screen.getByRole('combobox', { name: 'Employee' }));
    fireEvent.click(await screen.findByRole('option', { name: 'EMP-001 - Ayesha Rahman' }));
    fireEvent.change(screen.getByRole('combobox', { name: 'Status' }), {
      target: { value: 'PRESENT' },
    });
    fireEvent.change(screen.getByLabelText('In time'), { target: { value: '08:30' } });
    fireEvent.change(screen.getByLabelText('Out time'), { target: { value: '17:00' } });
    fireEvent.click(screen.getByRole('button', { name: 'Record attendance' }));

    await screen.findByRole('button', { name: 'Edit attendance' });
    expect(mocks.apiRequest).toHaveBeenCalledWith(
      '/api/v1/attendance',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"employee_id":1'),
      }),
    );

    fireEvent.click(screen.getByRole('button', { name: 'Edit attendance' }));
    fireEvent.change(screen.getByRole('combobox', { name: 'Status' }), {
      target: { value: 'LATE' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save attendance' }));

    await screen.findByText('Late');
    expect(mocks.apiRequest).toHaveBeenCalledWith(
      '/api/v1/attendance/4',
      expect.objectContaining({
        method: 'PATCH',
        body: expect.stringContaining('"status":"LATE"'),
      }),
    );
  });

  it('uploads the Excel workbook and displays per-row failures', async () => {
    const file = new File(['workbook bytes'], 'attendance.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });

    render(<AttendancePage />);
    fireEvent.change(await screen.findByLabelText('Import Excel'), {
      target: { files: [file] },
    });

    expect(await screen.findByText('Import complete: 1 created, 1 rejected.')).toBeInTheDocument();
    expect(screen.getByText('Row 3: Employee code not found')).toBeInTheDocument();
    await waitFor(() =>
      expect(mocks.apiRequest).toHaveBeenCalledWith(
        '/api/v1/attendance/import',
        expect.objectContaining({
          method: 'POST',
          headers: {
            'Content-Type':
              'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          },
          body: file,
        }),
      ),
    );
  });

  it('exports attendance for the selected date range', async () => {
    const createObjectURL = vi.fn(() => 'blob:attendance');
    const revokeObjectURL = vi.fn();
    const originalCreate = URL.createObjectURL;
    const originalRevoke = URL.revokeObjectURL;
    URL.createObjectURL = createObjectURL;
    URL.revokeObjectURL = revokeObjectURL;
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => undefined);

    render(<AttendancePage />);
    fireEvent.change(await screen.findByLabelText('From date'), {
      target: { value: '2026-10-01' },
    });
    fireEvent.change(screen.getByLabelText('To date'), {
      target: { value: '2026-10-16' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Export Excel' }));

    await waitFor(() =>
      expect(mocks.apiRequest).toHaveBeenCalledWith(
        '/api/v1/attendance/export?from_date=2026-10-01&to_date=2026-10-16',
        {},
        { responseType: 'blob' },
      ),
    );
    await waitFor(() => expect(createObjectURL).toHaveBeenCalledOnce());
    expect(click).toHaveBeenCalledOnce();
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:attendance');
    URL.createObjectURL = originalCreate;
    URL.revokeObjectURL = originalRevoke;
    click.mockRestore();
  });

  it('downloads the server-generated attendance template', async () => {
    const createObjectURL = vi.fn(() => 'blob:template');
    vi.stubGlobal('URL', {
      ...URL,
      createObjectURL,
      revokeObjectURL: vi.fn(),
    });
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => undefined);

    render(<AttendancePage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Download template' }));

    await waitFor(() =>
      expect(mocks.apiRequest).toHaveBeenCalledWith(
        '/api/v1/attendance/template',
        {},
        { responseType: 'blob' },
      ),
    );
    expect(createObjectURL).toHaveBeenCalledOnce();
    expect(click).toHaveBeenCalledOnce();
    vi.unstubAllGlobals();
    click.mockRestore();
  });
});
