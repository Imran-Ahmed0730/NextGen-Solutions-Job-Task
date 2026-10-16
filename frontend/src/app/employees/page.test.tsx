import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  apiRequest: vi.fn(),
  showErrorToast: vi.fn(),
  showSuccessToast: vi.fn(),
}));

vi.mock('sweetalert2', () => ({ default: { fire: vi.fn() } }));

vi.mock('@/components/auth/protected-page', () => ({
  ProtectedPage: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock('@/components/auth/session-shell', () => ({
  useSessionProfile: () => ({
    permissions: [
      'employees.read',
      'employees.create',
      'employees.update',
      'employees.delete',
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

import EmployeesPage from './page';

describe('EmployeesPage', () => {
  beforeEach(() => {
    mocks.apiRequest.mockReset();
    mocks.showErrorToast.mockReset();
    mocks.showSuccessToast.mockReset();
    mocks.apiRequest.mockResolvedValue([]);
  });

  it('rejects invalid mobile numbers before saving', async () => {
    render(<EmployeesPage />);

    await screen.findByRole('heading', { name: 'Employees' });
    fireEvent.click(screen.getByRole('button', { name: 'Add employee' }));
    fireEvent.change(screen.getByRole('textbox', { name: 'Employee code' }), {
      target: { value: 'EMP-001' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: 'Employee name' }), {
      target: { value: 'Ayesha Rahman' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: /Mobile/ }), {
      target: { value: '01712345678' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: 'Mobile' }), {
      target: { value: 'abc' },
    });
    fireEvent.change(screen.getByLabelText(/Joining date/), {
      target: { value: '2024-02-01' },
    });
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Monthly base salary' }), {
      target: { value: '25000.00' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create employee' }));

    expect(await screen.findByText(/valid Bangladesh mobile number/)).toBeInTheDocument();
    expect(mocks.apiRequest).toHaveBeenCalledTimes(1);
  });

  it('creates an employee and refreshes the employee register', async () => {
    const employee = {
      id: 1,
      code: 'EMP-001',
      name: 'Ayesha Rahman',
      mobile: '01712345678',
      email: null,
      designation: null,
      department: null,
      join_date: '2024-02-01',
      base_salary: '25000.00',
      is_active: true,
      deleted_at: null,
    };
    let listCalls = 0;
    let resolveInitial: ((result: typeof employee[]) => void) | undefined;
    mocks.apiRequest.mockImplementation((path: string, init?: RequestInit) => {
      if (init?.method === 'POST') return Promise.resolve(employee);
      listCalls += 1;
      if (listCalls === 1) {
        return new Promise((resolve) => {
          resolveInitial = resolve;
        });
      }
      return Promise.resolve([employee]);
    });

    render(<EmployeesPage />);

    await screen.findByRole('heading', { name: 'Employees' });
    await waitFor(() => expect(resolveInitial).toBeTypeOf('function'));
    fireEvent.click(screen.getByRole('button', { name: 'Add employee' }));
    fireEvent.change(screen.getByRole('textbox', { name: 'Employee code' }), {
      target: { value: 'EMP-001' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: 'Employee name' }), {
      target: { value: 'Ayesha Rahman' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: /Mobile/ }), {
      target: { value: '01712345678' },
    });
    fireEvent.change(screen.getByLabelText(/Joining date/), {
      target: { value: '2024-02-01' },
    });
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Monthly base salary' }), {
      target: { value: '25000.00' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create employee' }));

    await waitFor(() => expect(screen.getByText('Ayesha Rahman')).toBeInTheDocument());
    expect(screen.getByRole('button', { name: 'Edit Ayesha Rahman' })).toHaveAttribute(
      'title',
      'Edit Ayesha Rahman',
    );
    expect(screen.getByRole('button', { name: 'Delete Ayesha Rahman' })).toHaveAttribute(
      'title',
      'Delete Ayesha Rahman',
    );
    expect(mocks.apiRequest).toHaveBeenCalledWith(
      '/api/v1/employees',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"base_salary":"25000.00"'),
      }),
    );
    expect(mocks.apiRequest).toHaveBeenCalledWith(
      '/api/v1/employees',
      expect.objectContaining({ cache: 'no-store' }),
    );
    resolveInitial?.([]);
    expect(screen.getByText('Ayesha Rahman')).toBeInTheDocument();
    expect(mocks.showSuccessToast).toHaveBeenCalledWith('Employee created.');
  });
});
