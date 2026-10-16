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
    permissions: ['sales.quotations.read', 'sales.quotations.update', 'sales.orders.create'],
  }),
}));

vi.mock('@/lib/auth-api', () => ({
  apiRequest: mocks.apiRequest,
}));

vi.mock('@/lib/notifications', () => ({
  showErrorToast: mocks.showErrorToast,
  showSuccessToast: mocks.showSuccessToast,
}));

import QuotationsPage from './page';

describe('QuotationsPage', () => {
  beforeEach(() => {
    mocks.apiRequest.mockReset();
    mocks.showErrorToast.mockReset();
    mocks.showSuccessToast.mockReset();

    let quotation = {
      id: 9,
      doc_no: 'QT-20260001',
      doc_date: '2026-10-24',
      customer_id: 2,
      valid_until: null,
      status: 'DRAFT',
      subtotal: '20.00',
      discount: '0.00',
      total: '20.00',
      note: null,
      sales_order_id: null as number | null,
      lines: [
        {
          id: 1,
          product_id: 7,
          qty: '2.000',
          unit_price: '10.00',
          line_total: '20.00',
        },
      ],
    };

    mocks.apiRequest.mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/v1/sales/quotations/options') {
        return Promise.resolve({
          customers: [{ id: 2, code: 'CUS-1', name: 'Customer One' }],
          products: [
            { id: 7, sku: 'FG-001', name: 'Finished Good', unit_code: 'pcs', allow_decimal: true },
          ],
          warehouses: [{ id: 3, code: 'MAIN', name: 'Main Warehouse' }],
        });
      }
      if (path.startsWith('/api/v1/sales/quotations?')) {
        return Promise.resolve([quotation]);
      }
      if (path.endsWith('/send') || path.endsWith('/accept')) {
        quotation = { ...quotation, status: path.endsWith('/send') ? 'SENT' : 'ACCEPTED' };
        return Promise.resolve(quotation);
      }
      if (path.endsWith('/convert')) {
        quotation = { ...quotation, sales_order_id: 12 };
        return Promise.resolve({ id: 12, doc_no: 'SO-20260001' });
      }
      return Promise.resolve(null);
    });
  });

  it('sends and accepts a quotation, then converts it once to a Sales Order', async () => {
    render(<QuotationsPage />);

    fireEvent.click(await screen.findByRole('button', { name: 'Send' }));
    await screen.findByText('SENT');

    fireEvent.click(screen.getByRole('button', { name: 'Accept' }));
    await screen.findByText('ACCEPTED');

    fireEvent.click(screen.getByRole('button', { name: 'Convert' }));
    fireEvent.change(screen.getByRole('combobox', { name: 'Conversion warehouse' }), {
      target: { value: '3' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create Sales Order' }));

    await screen.findByText('Converted to Sales Order 12');
    await waitFor(() =>
      expect(mocks.apiRequest).toHaveBeenCalledWith(
        '/api/v1/sales/quotations/9/convert',
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"warehouse_id":3'),
        }),
      ),
    );
  });
});
