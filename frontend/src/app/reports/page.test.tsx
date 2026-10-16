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
  useSessionProfile: () => ({ permissions: ['reports.read'] }),
}));

vi.mock('@/lib/auth-api', () => ({ apiRequest: mocks.apiRequest }));
vi.mock('@/lib/notifications', () => ({ showErrorToast: mocks.showErrorToast }));

import ReportsPage from './page';

describe('ReportsPage', () => {
  beforeEach(() => {
    mocks.apiRequest.mockReset();
    mocks.showErrorToast.mockReset();
    mocks.apiRequest.mockResolvedValue({
      report_type: 'sales',
      title: 'Sales',
      period_from: '2026-10-17',
      period_to: '2026-10-17',
      columns: ['document', 'party', 'amount'],
      rows: [{ document: 'INV-1', party: 'Acme', amount: '125.00' }],
    });
  });

  it('loads a report and supports changing the report type', async () => {
    render(<ReportsPage />);

    expect(await screen.findByText('INV-1')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Report'), {
      target: { value: 'low_stock' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'View report' }));

    await waitFor(() =>
      expect(mocks.apiRequest).toHaveBeenLastCalledWith(
        expect.stringMatching(/^\/api\/v1\/reports\?report_type=low_stock&/),
      ),
    );
    expect(screen.getByRole('button', { name: 'Export CSV' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Print / PDF' })).toBeEnabled();
  });
});
