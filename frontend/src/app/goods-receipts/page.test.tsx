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
    permissions: ['purchase.receipts.read', 'purchase.receipts.create'],
  }),
}));

vi.mock('@/lib/auth-api', () => ({
  apiRequest: mocks.apiRequest,
}));

vi.mock('@/lib/notifications', () => ({
  showErrorToast: vi.fn(),
  showSuccessToast: vi.fn(),
}));

import GoodsReceiptsPage from './page';

describe('GoodsReceiptsPage', () => {
  beforeEach(() => {
    mocks.apiRequest.mockReset();
    const receipts: {
      id: number;
      doc_no: string;
      doc_date: string;
      po_id: number;
      supplier_id: number;
      warehouse_id: number;
      status: string;
      total: string;
      note: string | null;
      lines: {
        id: number;
        po_line_id: number;
        product_id: number;
        product_sku: string;
        product_name: string;
        qty: string;
        unit_cost: string;
        line_total: string;
      }[];
    }[] = [];
    mocks.apiRequest.mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/v1/purchase/receipts/options') {
        return Promise.resolve({
          orders: [
            {
              id: 5,
              doc_no: 'PO-20260005',
              doc_date: '2026-10-15',
              supplier_id: 2,
              supplier_name: 'Supplier One',
              warehouse_id: 3,
              warehouse_name: 'Main Warehouse',
              status: 'APPROVED',
              lines: [
                {
                  po_line_id: 8,
                  product_id: 7,
                  product_sku: 'RAW-001',
                  product_name: 'Raw Material',
                  unit_code: 'kg',
                  allow_decimal: true,
                  qty_ordered: '10.000',
                  received_qty: '0.000',
                  unit_price: '3.00',
                },
              ],
            },
          ],
        });
      }
      if (init?.method === 'POST') {
        const body = JSON.parse(String(init.body)) as {
          doc_date: string;
          po_id: number;
          note: string;
          lines: { po_line_id: number; qty: string; unit_cost: string }[];
        };
        const receipt = {
          id: 19,
          doc_no: 'GR-20260001',
          ...body,
          supplier_id: 2,
          warehouse_id: 3,
          status: 'POSTED',
          total: '30.00',
          lines: body.lines.map((line, index) => ({
            id: index + 1,
            product_id: 7,
            product_sku: 'RAW-001',
            product_name: 'Raw Material',
            ...line,
            line_total: '30.00',
          })),
        };
        receipts.push(receipt);
        return Promise.resolve(receipt);
      }
      if (path.startsWith('/api/v1/purchase/receipts?')) return Promise.resolve(receipts);
      return Promise.resolve(null);
    });
  });

  it('posts a goods receipt against an approved purchase order', async () => {
    render(<GoodsReceiptsPage />);

    await screen.findByRole('heading', { name: 'Post goods receipt' });
    fireEvent.change(screen.getByRole('combobox', { name: 'Purchase order' }), {
      target: { value: '5' },
    });
    expect(screen.getByRole('spinbutton', { name: 'Receive quantity 1' })).toHaveValue(10);
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Receive quantity 1' }), {
      target: { value: '4.000' },
    });
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Unit cost 1' }), {
      target: { value: '3.2500' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Post receipt' }));

    await screen.findByText('GR-20260001');
    expect(mocks.apiRequest).toHaveBeenCalledWith(
      '/api/v1/purchase/receipts',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"unit_cost":"3.2500"'),
      }),
    );
    await waitFor(() => {
      expect(mocks.apiRequest).toHaveBeenCalledWith(
        '/api/v1/purchase/receipts?offset=0&limit=51',
      );
    });
  });

  it('does not offer a negative remaining quantity when received quantity exceeds ordered', async () => {
    mocks.apiRequest.mockImplementation((path: string) => {
      if (path === '/api/v1/purchase/receipts/options') {
        return Promise.resolve({
          orders: [
            {
              id: 5,
              doc_no: 'PO-20260005',
              doc_date: '2026-10-15',
              supplier_id: 2,
              supplier_name: 'Supplier One',
              warehouse_id: 3,
              warehouse_name: 'Main Warehouse',
              status: 'PARTIALLY_RECEIVED',
              lines: [
                {
                  po_line_id: 8,
                  product_id: 7,
                  product_sku: 'RAW-001',
                  product_name: 'Raw Material',
                  unit_code: 'kg',
                  allow_decimal: true,
                  qty_ordered: '10.000',
                  received_qty: '10.500',
                  unit_price: '3.00',
                },
              ],
            },
          ],
        });
      }
      return Promise.resolve([]);
    });

    render(<GoodsReceiptsPage />);
    await screen.findByRole('heading', { name: 'Post goods receipt' });
    fireEvent.change(screen.getByRole('combobox', { name: 'Purchase order' }), {
      target: { value: '5' },
    });

    expect(screen.getByRole('spinbutton', { name: 'Receive quantity 1' })).toHaveValue(null);
  });
});
