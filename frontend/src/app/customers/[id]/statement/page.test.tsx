import { fireEvent, render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  apiRequest: vi.fn(),
  showErrorToast: vi.fn(),
  print: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useParams: () => ({ id: '3' }),
}));

vi.mock('@/components/auth/protected-page', () => ({
  ProtectedPage: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock('@/lib/auth-api', () => ({
  apiRequest: mocks.apiRequest,
  getApiUrl: (path: string) => `http://localhost:8000${path}`,
}));

vi.mock('@/lib/notifications', () => ({
  showErrorToast: mocks.showErrorToast,
}));

import CustomerStatementPage from './page';

describe('CustomerStatementPage', () => {
  beforeEach(() => {
    mocks.apiRequest.mockReset();
    mocks.showErrorToast.mockReset();
    mocks.print.mockReset();
    Object.defineProperty(window, 'print', { configurable: true, value: mocks.print });
    mocks.apiRequest.mockImplementation((path: string) => {
      if (path === '/api/v1/customers/3/statement') {
        return Promise.resolve({
          customer_id: 3,
          customer_name: 'Acme Stores',
          opening_due: '10.00',
          balance: '25.00',
          entries: [
            {
              date: '2026-10-25',
              type: 'INVOICE',
              description: 'Invoice INV-001',
              amount: '15.00',
              balance: '25.00',
            },
          ],
        });
      }
      return Promise.resolve({
        company_name: 'Sabuj Pran Ltd.',
        company_logo_path: '/brand/company-logo.svg',
      });
    });
  });

  it('prints the customer statement with the company branding', async () => {
    render(<CustomerStatementPage />);

    expect(await screen.findByText('Acme Stores')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Sabuj Pran Ltd.' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Print / Save as PDF' }));

    expect(mocks.apiRequest).toHaveBeenCalledWith('/api/v1/customers/3/statement');
    expect(mocks.print).toHaveBeenCalledOnce();
  });
});
