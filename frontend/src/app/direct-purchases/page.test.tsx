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
    permissions: ['purchase.direct_purchases.read', 'purchase.direct_purchases.create'],
  }),
}));

vi.mock('@/lib/auth-api', () => ({
  apiRequest: mocks.apiRequest,
}));

vi.mock('@/lib/notifications', () => ({
  showErrorToast: vi.fn(),
  showSuccessToast: vi.fn(),
}));

import DirectPurchasesPage from './page';

describe('DirectPurchasesPage', () => {
  beforeEach(() => {
    mocks.apiRequest.mockReset();
    const purchases: {
      id: number;
      doc_no: string;
      doc_date: string;
      supplier_id: number;
      warehouse_id: number;
      status: string;
      total: string;
      paid_amount: string;
      money_account_id: number | null;
      note: string | null;
      lines: {
        id: number;
        product_id: number;
        product_sku: string;
        product_name: string;
        qty: string;
        unit_cost: string;
        line_total: string;
      }[];
    }[] = [];
    mocks.apiRequest.mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/v1/purchase/direct-purchases/options') {
        return Promise.resolve({
          suppliers: [{ id: 2, code: 'SUP-01', name: 'Supplier One' }],
          warehouses: [{ id: 3, code: 'MAIN', name: 'Main Warehouse' }],
          products: [
            {
              id: 7,
              sku: 'RAW-001',
              name: 'Raw Material',
              unit_code: 'kg',
              allow_decimal: true,
            },
          ],
        });
      }
      if (init?.method === 'POST') {
        const body = JSON.parse(String(init.body)) as {
          doc_date: string;
          supplier_id: number;
          warehouse_id: number;
          note: string;
          lines: { product_id: number; qty: string; unit_cost: string }[];
        };
        const purchase = {
          id: 19,
          doc_no: 'DP-20260001',
          ...body,
          status: 'POSTED',
          total: '13.00',
          paid_amount: '0.00',
          money_account_id: null,
          lines: body.lines.map((line, index) => ({
            id: index + 1,
            product_sku: 'RAW-001',
            product_name: 'Raw Material',
            line_total: '13.00',
            ...line,
          })),
        };
        purchases.push(purchase);
        return Promise.resolve(purchase);
      }
      if (path.startsWith('/api/v1/purchase/direct-purchases?')) {
        return Promise.resolve(purchases);
      }
      return Promise.resolve(null);
    });
  });

  it('posts a direct purchase on credit and refreshes its history', async () => {
    render(<DirectPurchasesPage />);

    await screen.findByRole('heading', { name: 'Post direct purchase' });
    fireEvent.change(screen.getByRole('combobox', { name: 'Supplier' }), {
      target: { value: '2' },
    });
    fireEvent.change(screen.getByRole('combobox', { name: 'Warehouse' }), {
      target: { value: '3' },
    });
    fireEvent.change(screen.getByRole('combobox', { name: 'Product 1' }), {
      target: { value: '7' },
    });
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Quantity 1' }), {
      target: { value: '4.000' },
    });
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Unit cost 1' }), {
      target: { value: '3.2500' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Post purchase on credit' }));

    await screen.findByText('DP-20260001');
    expect(mocks.apiRequest).toHaveBeenCalledWith(
      '/api/v1/purchase/direct-purchases',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"unit_cost":"3.2500"'),
      }),
    );
    await waitFor(() => {
      expect(mocks.apiRequest).toHaveBeenCalledWith(
        '/api/v1/purchase/direct-purchases?offset=0&limit=51',
      );
    });
  });
});
