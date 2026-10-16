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
    permissions: ['approvals.rules.read', 'approvals.rules.create', 'approvals.rules.update'],
  }),
}));

vi.mock('@/lib/auth-api', () => ({ apiRequest: mocks.apiRequest }));
vi.mock('@/lib/notifications', () => ({
  showErrorToast: mocks.showErrorToast,
  showSuccessToast: mocks.showSuccessToast,
}));

import ApprovalRulesPage from './page';

describe('ApprovalRulesPage', () => {
  beforeEach(() => {
    mocks.apiRequest.mockReset();
    mocks.showErrorToast.mockReset();
    mocks.showSuccessToast.mockReset();
    let rules: Record<string, unknown>[] = [];
    const activeRule = {
      id: 5,
      doc_type: 'PURCHASE_ORDER',
      min_amount: '1000.00',
      max_amount: '5000.00',
      approver_role_id: 2,
      approver_role: { id: 2, name: 'Finance Approver' },
      is_active: true,
    };
    mocks.apiRequest.mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/v1/approvals/rules/options/roles') {
        return Promise.resolve([{ id: 2, name: 'Finance Approver' }]);
      }
      if (path === '/api/v1/approvals/rules?include_inactive=true') {
        return Promise.resolve(rules);
      }
      if (path === '/api/v1/approvals/rules' && init?.method === 'POST') {
        rules = [activeRule];
        return Promise.resolve(activeRule);
      }
      if (path === '/api/v1/approvals/rules/5/deactivate') {
        const inactiveRule = { ...activeRule, is_active: false };
        rules = [inactiveRule];
        return Promise.resolve(inactiveRule);
      }
      return Promise.resolve([]);
    });
  });

  it('creates and deactivates a threshold rule', async () => {
    render(<ApprovalRulesPage />);
    await screen.findByRole('heading', { name: 'Approval Rules' });

    fireEvent.change(screen.getByRole('combobox', { name: /Document type/ }), {
      target: { value: 'PURCHASE_ORDER' },
    });
    fireEvent.change(screen.getByRole('spinbutton', { name: /Minimum amount/ }), {
      target: { value: '1000.00' },
    });
    fireEvent.change(screen.getByRole('spinbutton', { name: /Maximum amount/ }), {
      target: { value: '5000.00' },
    });
    fireEvent.change(screen.getByRole('combobox', { name: /Approver role/ }), {
      target: { value: '2' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create rule' }));

    await screen.findByText('Purchase order');
    expect(mocks.apiRequest).toHaveBeenCalledWith(
      '/api/v1/approvals/rules',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          doc_type: 'PURCHASE_ORDER',
          min_amount: '1000.00',
          max_amount: '5000.00',
          approver_role_id: 2,
        }),
      }),
    );

    fireEvent.click(
      screen.getByRole('button', { name: 'Deactivate Purchase order approval rule' }),
    );
    await screen.findByText('Inactive');
    await waitFor(() =>
      expect(mocks.apiRequest).toHaveBeenCalledWith(
        '/api/v1/approvals/rules/5/deactivate',
        { method: 'POST' },
      ),
    );
  });
});
