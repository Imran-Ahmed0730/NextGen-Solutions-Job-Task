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
      'employees.payroll.read',
      'employees.payroll.create',
      'employees.payroll.update',
      'employees.payroll.post',
    ],
  }),
}));

vi.mock('@/lib/auth-api', () => ({ apiRequest: mocks.apiRequest }));
vi.mock('@/lib/notifications', () => ({
  showErrorToast: mocks.showErrorToast,
  showSuccessToast: mocks.showSuccessToast,
}));

import PayrollPage from './page';

describe('PayrollPage', () => {
  beforeEach(() => {
    mocks.apiRequest.mockReset();
    mocks.showErrorToast.mockReset();
    mocks.showSuccessToast.mockReset();
    let runs: Record<string, unknown>[] = [];
    const draft = {
      id: 1,
      doc_no: null,
      period_month: 10,
      period_year: 2026,
      status: 'DRAFT',
      total_amount: '1000.00',
      paid_on: null,
      account_id: null,
      lines: [
        {
          id: 3,
          employee_id: 7,
          employee: { id: 7, code: 'EMP-001', name: 'Ayesha Rahman', department: 'HR' },
          base_salary: '1000.00',
          deductions: '0.00',
          net_pay: '1000.00',
          paid_txn_id: null,
        },
      ],
    };
    mocks.apiRequest.mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/v1/payroll/options') {
        return Promise.resolve({ accounts: [{ id: 2, name: 'Main Bank', type: 'BANK' }] });
      }
      if (path === '/api/v1/payroll/runs?limit=100') return Promise.resolve(runs);
      if (path === '/api/v1/payroll/runs' && init?.method === 'POST') {
        runs = [draft];
        return Promise.resolve(draft);
      }
      if (path === '/api/v1/payroll/runs/1/lines/3' && init?.method === 'PATCH') {
        const updated = {
          ...draft,
          total_amount: '900.00',
          lines: [{ ...draft.lines[0], deductions: '100.00', net_pay: '900.00' }],
        };
        runs = [updated];
        return Promise.resolve(updated);
      }
      if (path === '/api/v1/payroll/runs/1/post' && init?.method === 'POST') {
        const posted = {
          ...draft,
          doc_no: 'PAY-20260001',
          status: 'POSTED',
          total_amount: '900.00',
          paid_on: '2026-10-31',
          account_id: 2,
          lines: [
            {
              ...draft.lines[0],
              deductions: '100.00',
              net_pay: '900.00',
              paid_txn_id: 99,
            },
          ],
        };
        runs = [posted];
        return Promise.resolve(posted);
      }
      return Promise.resolve([]);
    });
  });

  it('creates a payroll draft, saves deductions, then posts salaries', async () => {
    render(<PayrollPage />);
    await screen.findByRole('heading', { name: 'Basic Payroll' });
    fireEvent.change(screen.getByLabelText(/Payroll month/), { target: { value: '10' } });
    fireEvent.change(screen.getByLabelText(/Payroll year/), { target: { value: '2026' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create payroll draft' }));

    await screen.findByText('Ayesha Rahman');
    expect(mocks.apiRequest).toHaveBeenCalledWith(
      '/api/v1/payroll/runs',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ period_month: 10, period_year: 2026 }),
      }),
    );

    fireEvent.change(screen.getByRole('spinbutton', { name: 'Deductions for Ayesha Rahman' }), {
      target: { value: '100.00' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save deduction' }));
    await screen.findByText('BDT 900.00');
    expect(mocks.apiRequest).toHaveBeenCalledWith(
      '/api/v1/payroll/runs/1/lines/3',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ deductions: '100.00' }),
      }),
    );

    fireEvent.change(screen.getByLabelText(/Payment date/), {
      target: { value: '2026-10-31' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Post salary payments' }));
    await screen.findByText('Paid 2026-10-31 from Main Bank.');
    await waitFor(() =>
      expect(mocks.apiRequest).toHaveBeenCalledWith(
        '/api/v1/payroll/runs/1/post',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ account_id: 2, paid_on: '2026-10-31' }),
        }),
      ),
    );
  });
});
