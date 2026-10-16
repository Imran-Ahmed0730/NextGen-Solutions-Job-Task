import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  apiRequest: vi.fn(),
  showErrorToast: vi.fn(),
}));

vi.mock('@/components/auth/protected-page', () => ({
  ProtectedPage: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock('@/components/auth/session-shell', () => ({
  useSessionProfile: () => ({ permissions: ['reports.dashboard.read'] }),
}));

vi.mock('@/lib/auth-api', () => ({ apiRequest: mocks.apiRequest }));
vi.mock('@/lib/notifications', () => ({ showErrorToast: mocks.showErrorToast }));

import DashboardPage from './page';

describe('DashboardPage', () => {
  beforeEach(() => {
    mocks.apiRequest.mockReset();
    mocks.showErrorToast.mockReset();
    mocks.apiRequest.mockResolvedValue({
      period_from: '2026-10-17',
      period_to: '2026-10-17',
      sales: '250.00',
      collections: '100.00',
      expenses: '25.00',
      purchases: '50.00',
      account_balances: { CASH: '500.00', BANK: '1000.00', MFS: '75.00' },
      customer_due: '300.00',
      supplier_due: '200.00',
      inventory_value: '1250.00',
      pending_orders: 2,
      estimated_profit: '125.00',
    });
  });

  it('loads dashboard KPIs and applies a selected reporting period', async () => {
    render(<DashboardPage />);
    await screen.findByRole('heading', { name: 'Management Dashboard' });
    await screen.findByText('2', { selector: 'p' });
    expect(screen.getByText('500.00')).toBeInTheDocument();
    expect(screen.getByText('1,000.00')).toBeInTheDocument();
    expect(screen.getByText('75.00')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('From date'), {
      target: { value: '2026-10-01' },
    });
    fireEvent.change(screen.getByLabelText('To date'), {
      target: { value: '2026-10-15' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Apply period' }));

    await waitFor(() =>
      expect(mocks.apiRequest).toHaveBeenLastCalledWith(
        '/api/v1/reports/dashboard?period_from=2026-10-01&period_to=2026-10-15',
      ),
    );
  });
});
