import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  apiRequest: vi.fn(),
}));

vi.mock('@/components/auth/protected-page', () => ({
  ProtectedPage: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock('@/components/auth/session-shell', () => ({
  useSessionProfile: () => ({
    permissions: ['sales.returns.read', 'sales.returns.create'],
  }),
}));

vi.mock('@/lib/auth-api', () => ({
  apiRequest: mocks.apiRequest,
}));

vi.mock('@/lib/notifications', () => ({
  showErrorToast: vi.fn(),
  showSuccessToast: vi.fn(),
}));

import SalesReturnsPage from './page';

describe('SalesReturnsPage', () => {
  beforeEach(() => {
    mocks.apiRequest.mockReset();
    const returns: {
      id: number;
      doc_no: string;
      doc_date: string;
      invoice_id: number;
      invoice_doc_no: string;
      customer_id: number;
      warehouse_id: number;
      status: string;
      total: string;
      note: string | null;
      lines: {
        id: number;
        invoice_line_id: number;
        product_id: number;
        product_sku: string;
        product_name: string;
        qty: string;
        unit_code: string;
        unit_price: string;
        line_total: string;
        unit_cost_cogs: string;
      }[];
    }[] = [];
    mocks.apiRequest.mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/v1/sales/returns/options') {
        return Promise.resolve({
          invoices: [
            {
              id: 4,
              doc_no: 'INV-20260004',
              doc_date: '2026-10-25',
              lines: [
                {
                  invoice_line_id: 9,
                  product_id: 7,
                  product_sku: 'FG-001',
                  product_name: 'Finished Product',
                  unit_code: 'pc',
                  allow_decimal: true,
                  qty_invoiced: '2.000',
                  qty_returned: '0.000',
                  qty_available: '2.000',
                  unit_price: '10.00',
                  unit_cost_cogs: '2.5000',
                },
              ],
            },
          ],
        });
      }
      if (init?.method === 'POST') {
        const body = JSON.parse(String(init.body)) as {
          doc_date: string;
          invoice_id: number;
          note: string;
          lines: { invoice_line_id: number; qty: string }[];
        };
        const posted = {
          id: 11,
          doc_no: 'SR-20260001',
          invoice_doc_no: 'INV-20260004',
          customer_id: 2,
          warehouse_id: 3,
          status: 'POSTED',
          total: '9.00',
          doc_date: body.doc_date,
          invoice_id: body.invoice_id,
          note: body.note,
          lines: body.lines.map((line, index) => ({
            id: index + 1,
            product_id: 7,
            product_sku: 'FG-001',
            product_name: 'Finished Product',
            unit_code: 'pc',
            unit_price: '10.00',
            line_total: '9.00',
            unit_cost_cogs: '2.5000',
            ...line,
          })),
        };
        returns.push(posted);
        return Promise.resolve(posted);
      }
      if (path.startsWith('/api/v1/sales/returns?')) return Promise.resolve(returns);
      return Promise.resolve(null);
    });
  });

  it('posts a return against an invoice and refreshes history', async () => {
    render(<SalesReturnsPage />);

    await screen.findByRole('heading', { name: 'Post sales return' });
    fireEvent.change(screen.getByRole('combobox', { name: 'Invoice' }), {
      target: { value: '4' },
    });
    expect(screen.getByText(/Original price 10\.00 · COGS 2\.5000/)).toBeInTheDocument();
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Return quantity 1' }), {
      target: { value: '1.000' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Post return' }));

    await screen.findByText('SR-20260001');
    expect(mocks.apiRequest).toHaveBeenCalledWith(
      '/api/v1/sales/returns',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"invoice_line_id":9'),
      }),
    );
    await waitFor(() => {
      expect(mocks.apiRequest).toHaveBeenCalledWith('/api/v1/sales/returns?offset=0&limit=51');
    });
  });
});
