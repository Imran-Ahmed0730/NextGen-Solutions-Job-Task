import { fireEvent, render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  apiRequest: vi.fn(),
  showErrorToast: vi.fn(),
  print: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useParams: () => ({ id: '5' }),
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

import SupplierStatementPage from './page';

describe('SupplierStatementPage', () => {
  beforeEach(() => {
    mocks.apiRequest.mockReset();
    mocks.showErrorToast.mockReset();
    mocks.print.mockReset();
    Object.defineProperty(window, 'print', { configurable: true, value: mocks.print });
    mocks.apiRequest.mockImplementation((path: string) => {
      if (path === '/api/v1/suppliers/5/statement') {
        return Promise.resolve({
          supplier_id: 5,
          supplier_name: 'Northwind Supply',
          opening_due: '4.00',
          balance: '12.00',
          entries: [
            {
              date: '2026-10-25',
              type: 'PURCHASE',
              description: 'Purchase PUR-001',
              amount: '8.00',
              balance: '12.00',
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

  it('prints the supplier statement with the company branding', async () => {
    render(<SupplierStatementPage />);

    expect(await screen.findByText('Northwind Supply')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Sabuj Pran Ltd.' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Print / Save as PDF' }));

    expect(mocks.apiRequest).toHaveBeenCalledWith('/api/v1/suppliers/5/statement');
    expect(mocks.print).toHaveBeenCalledOnce();
  });
});
