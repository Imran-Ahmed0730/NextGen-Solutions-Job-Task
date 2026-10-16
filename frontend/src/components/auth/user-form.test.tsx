import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  apiRequest: vi.fn(),
  push: vi.fn(),
  showErrorToast: vi.fn(),
  showSuccessToast: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mocks.push }),
}));

vi.mock('@/components/auth/protected-page', () => ({
  ProtectedPage: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock('@/components/auth/session-shell', () => ({
  useSessionProfile: () => ({ permissions: ['employees.read'] }),
}));

vi.mock('@/lib/auth-api', () => ({ apiRequest: mocks.apiRequest }));
vi.mock('@/lib/notifications', () => ({
  showErrorToast: mocks.showErrorToast,
  showSuccessToast: mocks.showSuccessToast,
}));

import { UserForm } from './user-form';

describe('UserForm', () => {
  beforeEach(() => {
    mocks.apiRequest.mockReset();
    mocks.push.mockReset();
    mocks.showErrorToast.mockReset();
    mocks.showSuccessToast.mockReset();
    mocks.apiRequest.mockImplementation(async (path: string) => {
      if (path === '/api/v1/auth/roles') return [];
      if (path === '/api/v1/employees?limit=200') {
        return [{ id: 8, code: 'EMP-008', name: 'Ayesha Rahman' }];
      }
      return {};
    });
  });

  it('saves a selected employee association', async () => {
    render(<UserForm userId={null} />);

    fireEvent.change(screen.getByRole('textbox', { name: 'Username' }), {
      target: { value: 'ayesha' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: 'Full name' }), {
      target: { value: 'Ayesha Rahman' },
    });
    const employeeOption = await screen.findByRole('option', {
      name: 'EMP-008 — Ayesha Rahman',
    });
    fireEvent.change(screen.getByLabelText('Linked employee'), {
      target: { value: employeeOption.getAttribute('value') },
    });
    fireEvent.change(screen.getByLabelText(/Initial password/), {
      target: { value: 'Secure-Password-123' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save user' }));

    await waitFor(() =>
      expect(mocks.apiRequest).toHaveBeenCalledWith(
        '/api/v1/auth/users',
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"employee_id":8'),
        }),
      ),
    );
  });
});
