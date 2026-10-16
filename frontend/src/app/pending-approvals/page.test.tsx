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
    permissions: ['approvals.requests.read', 'approvals.requests.decide'],
  }),
}));

vi.mock('@/lib/auth-api', () => ({ apiRequest: mocks.apiRequest }));
vi.mock('@/lib/notifications', () => ({
  showErrorToast: mocks.showErrorToast,
  showSuccessToast: mocks.showSuccessToast,
}));

import PendingApprovalsPage from './page';

describe('PendingApprovalsPage', () => {
  beforeEach(() => {
    mocks.apiRequest.mockReset();
    mocks.showErrorToast.mockReset();
    mocks.showSuccessToast.mockReset();
    const row = {
      id: 9,
      doc_type: 'EXPENSE',
      doc_id: 4,
      doc_no: 'EXP-20260001',
      doc_status: 'PENDING_APPROVAL',
      amount: '250.00',
      requested_by: 3,
      requester_name: 'Finance Clerk',
      approver_role_id: 2,
      approver_role_name: 'Finance Approver',
      requested_at: '2026-10-15T09:00:00',
      status: 'PENDING',
    };
    let pending = [row];
    mocks.apiRequest.mockImplementation((path: string) => {
      if (path === '/api/v1/approvals/requests?limit=100') return Promise.resolve(pending);
      if (path === '/api/v1/approvals/requests/9/approve') {
        pending = [];
        return Promise.resolve({ ...row, status: 'APPROVED' });
      }
      return Promise.resolve([]);
    });
  });

  it('shows assigned requests and approves with the entered note', async () => {
    render(<PendingApprovalsPage />);
    await screen.findByText('EXP-20260001');
    expect(screen.getByText('Finance Clerk')).toBeInTheDocument();
    expect(screen.getByText('250.00')).toBeInTheDocument();
    fireEvent.change(screen.getByRole('textbox', { name: 'Decision note for EXP-20260001' }), {
      target: { value: 'Reviewed and approved' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Approve' }));

    await waitFor(() =>
      expect(mocks.apiRequest).toHaveBeenCalledWith(
        '/api/v1/approvals/requests/9/approve',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ note: 'Reviewed and approved' }),
        }),
      ),
    );
    await screen.findByText('There are no pending approvals for your roles.');
  });
});
