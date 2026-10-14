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
    permissions: ['purchase.returns.read', 'purchase.returns.create'],
  }),
}));

vi.mock('@/lib/auth-api', () => ({
  apiRequest: mocks.apiRequest,
}));

vi.mock('@/lib/notifications', () => ({
  showErrorToast: vi.fn(),
  showSuccessToast: vi.fn(),
}));

import PurchaseReturnsPage from './page';

describe('PurchaseReturnsPage', () => {
  beforeEach(() => {
    mocks.apiRequest.mockReset();
    const returns: {
      id: number;
      doc_no: string;
      doc_date: string;
      receipt_id: number;
      receipt_doc_no: string;
      supplier_id: number;
      warehouse_id: number;
      status: string;
      total: string;
      note: string | null;
      lines: {
        id: number;
        receipt_line_id: number;
        product_id: number;
        product_sku: string;
        product_name: string;
        qty: string;
        unit_cost: string;
        line_total: string;
      }[];
    }[] = [];
    mocks.apiRequest.mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/v1/purchase/returns/options') {
        return Promise.resolve({
          receipts: [
            {
              id: 5,
              doc_no: 'GR-20260005',
              doc_date: '2026-10-17',
              supplier_id: 2,
              supplier_name: 'Supplier One',
              warehouse_id: 3,
              warehouse_name: 'Main Warehouse',
              lines: [
                {
                  receipt_line_id: 8,
                  product_id: 7,
                  product_sku: 'RAW-001',
                  product_name: 'Raw Material',
                  unit_code: 'kg',
                  allow_decimal: true,
                  qty_received: '10.000',
                  qty_returned: '0.000',
                  qty_available: '10.000',
                  unit_cost: '4.2500',
                },
              ],
            },
          ],
        });
      }
      if (init?.method === 'POST') {
        const body = JSON.parse(String(init.body)) as {
          doc_date: string;
          receipt_id: number;
          note: string;
          lines: { receipt_line_id: number; qty: string }[];
        };
        const purchaseReturn = {
          id: 19,
          doc_no: 'PR-20260001',
          receipt_doc_no: 'GR-20260005',
          ...body,
          supplier_id: 2,
          warehouse_id: 3,
          status: 'POSTED',
          total: '12.75',
          lines: body.lines.map((line, index) => ({
            id: index + 1,
            product_id: 7,
            product_sku: 'RAW-001',
            product_name: 'Raw Material',
            unit_cost: '4.2500',
            line_total: '12.75',
            ...line,
          })),
        };
        returns.push(purchaseReturn);
        return Promise.resolve(purchaseReturn);
      }
      if (path.startsWith('/api/v1/purchase/returns?')) return Promise.resolve(returns);
      return Promise.resolve(null);
    });
  });

  it('posts a return at original receipt cost and refreshes history', async () => {
    render(<PurchaseReturnsPage />);

    await screen.findByRole('heading', { name: 'Post purchase return' });
    fireEvent.change(screen.getByRole('combobox', { name: 'Goods Receipt' }), {
      target: { value: '5' },
    });
    expect(screen.getByText(/Original unit cost 4\.2500/)).toBeInTheDocument();
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Return quantity 1' }), {
      target: { value: '3.000' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Post return' }));

    await screen.findByText('PR-20260001');
    expect(mocks.apiRequest).toHaveBeenCalledWith(
      '/api/v1/purchase/returns',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"receipt_line_id":8'),
      }),
    );
    await waitFor(() => {
      expect(mocks.apiRequest).toHaveBeenCalledWith('/api/v1/purchase/returns?offset=0&limit=51');
    });
  });
});
