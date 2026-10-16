import { render, screen } from '@testing-library/react';
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
  useSessionProfile: () => ({ permissions: ['auth.audit_logs.read'] }),
}));

vi.mock('@/lib/auth-api', () => ({ apiRequest: mocks.apiRequest }));
vi.mock('@/lib/notifications', () => ({ showErrorToast: mocks.showErrorToast }));

import AuditLogsPage from './page';

describe('AuditLogsPage', () => {
  beforeEach(() => {
    mocks.apiRequest.mockReset();
    mocks.showErrorToast.mockReset();
    mocks.apiRequest.mockResolvedValue([
      {
        id: 3,
        user_id: 7,
        entity_type: 'expense',
        entity_id: '12',
        action: 'CREATE',
        before_json: null,
        after_json: { amount: '25.00' },
        ip: '127.0.0.1',
        created_at: '2026-10-17T00:00:00Z',
      },
    ]);
  });

  it('shows recent audit history and before/after details', async () => {
    render(<AuditLogsPage />);

    expect(await screen.findByText('expense #12')).toBeInTheDocument();
    expect(screen.getByText('CREATE')).toBeInTheDocument();
    expect(screen.getByText('View details')).toBeInTheDocument();
    expect(mocks.apiRequest).toHaveBeenCalledWith('/api/v1/auth/audit-logs?offset=0&limit=200');
  });
});
