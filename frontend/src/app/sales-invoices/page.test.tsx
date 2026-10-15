import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  apiRequest: vi.fn(),
  showToast: vi.fn(),
}));

vi.mock('@/components/auth/protected-page', () => ({
  ProtectedPage: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock('@/components/auth/session-shell', () => ({
  useSessionProfile: () => ({
    permissions: ['sales.invoices.read', 'sales.invoices.create'],
  }),
}));

vi.mock('@/lib/auth-api', () => ({
  apiRequest: mocks.apiRequest,
}));

vi.mock('@/lib/notifications', () => ({
  showErrorToast: vi.fn(),
  showSuccessToast: vi.fn(),
  showToast: mocks.showToast,
}));

import SalesInvoicesPage from './page';

describe('SalesInvoicesPage', () => {
  beforeEach(() => {
    mocks.apiRequest.mockReset();
    mocks.showToast.mockReset();
    mocks.apiRequest.mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/v1/sales/invoices/options') {
        return Promise.resolve({
          deliveries: [
            { id: 4, doc_no: 'DN-0001', doc_date: '2026-10-25', order_doc_no: 'SO-0001' },
          ],
        });
      }
      if (path === '/api/v1/sales/invoices?limit=50') return Promise.resolve([]);
      if (path === '/api/v1/sales/invoices' && init?.method === 'POST') {
        return Promise.resolve({
          invoice: {
            id: 7,
            doc_no: 'INV-0001',
            doc_date: '2026-10-25',
            due_date: '2026-11-05',
            customer_id: 3,
            delivery_id: 4,
            status: 'POSTED',
            subtotal: '15.00',
            discount: '0.00',
            total: '15.00',
            cogs_total: '7.50',
            lines: [],
          },
          credit_limit_warning: true,
        });
      }
      return Promise.resolve(null);
    });
  });

  it('posts an invoice from a delivery and warns when the credit limit is exceeded', async () => {
    render(<SalesInvoicesPage />);

    await screen.findByRole('heading', { name: 'Sales Invoices' });
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Post invoice' })).not.toBeDisabled(),
    );
    fireEvent.change(screen.getByRole('combobox', { name: 'Posted delivery' }), {
      target: { value: '4' },
    });
    fireEvent.change(screen.getByLabelText('Due date'), {
      target: { value: '2026-11-05' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Post invoice' }));

    await waitFor(() => {
      expect(mocks.apiRequest).toHaveBeenCalledWith(
        '/api/v1/sales/invoices',
        expect.objectContaining({ method: 'POST' }),
      );
    });
    const request = mocks.apiRequest.mock.calls.find(
      ([path, init]) => path === '/api/v1/sales/invoices' && init?.method === 'POST',
    );
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({
      delivery_id: 4,
      doc_date: expect.any(String),
      due_date: '2026-11-05',
    });
    expect(mocks.showToast).toHaveBeenCalledWith(
      'warning',
      'Credit limit exceeded',
      'The invoice was posted in WARN mode.',
    );
  });
});
