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

  it('creates an employee and reloads the employee register', async () => {
    render(<EmployeesPage />);

    await screen.findByRole('heading', { name: 'Employees' });
    fireEvent.click(screen.getByRole('button', { name: 'Add employee' }));
    fireEvent.change(screen.getByRole('textbox', { name: 'Employee code' }), {
      target: { value: 'EMP-001' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: 'Employee name' }), {
      target: { value: 'Ayesha Rahman' },
    });
    fireEvent.change(screen.getByLabelText(/Joining date/), {
      target: { value: '2024-02-01' },
    });
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Monthly base salary' }), {
      target: { value: '25000.00' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create employee' }));

    await waitFor(() =>
      expect(mocks.apiRequest).toHaveBeenCalledWith(
        '/api/v1/employees',
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"base_salary":"25000.00"'),
        }),
      ),
    );
    expect(mocks.showSuccessToast).toHaveBeenCalledWith('Employee created.');
  });
});
