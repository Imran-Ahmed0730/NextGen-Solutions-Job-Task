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
    permissions: ['purchase.orders.read', 'purchase.orders.create', 'purchase.orders.update'],
  }),
}));

vi.mock('@/lib/auth-api', () => ({
  apiRequest: mocks.apiRequest,
}));

vi.mock('@/lib/notifications', () => ({
  showErrorToast: vi.fn(),
  showSuccessToast: vi.fn(),
}));

import PurchaseOrdersPage from './page';

describe('PurchaseOrdersPage', () => {
  beforeEach(() => {
    mocks.apiRequest.mockReset();
    const savedOrders: {
      id: number;
      doc_no: string;
      doc_date: string;
      supplier_id: number;
      warehouse_id: number;
      status: string;
      expected_date: string | null;
      subtotal: string;
      discount: string;
      total: string;
      note: string | null;
      lines: {
        id: number;
        product_id: number;
        qty: string;
        unit_price: string;
        line_total: string;
        received_qty: string;
      }[];
    }[] = [];
    mocks.apiRequest.mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/v1/purchase/orders/options') {
        return Promise.resolve({
          suppliers: [{ id: 2, code: 'SUP-1', name: 'Supplier One' }],
          warehouses: [{ id: 3, code: 'MAIN', name: 'Main Warehouse' }],
          products: [
            { id: 7, sku: 'RAW-001', name: 'Raw Material', unit_code: 'kg', allow_decimal: true },
          ],
        });
      }
      if (init?.method === 'POST') {
        const body = JSON.parse(String(init.body)) as {
          doc_date: string;
          supplier_id: number;
          warehouse_id: number;
          expected_date: string | null;
          discount: string;
          note: string;
          lines: { product_id: number; qty: string; unit_price: string }[];
        };
        const order = {
          id: 11,
          doc_no: 'PO-20260001',
          ...body,
          status: 'DRAFT',
          subtotal: '25.00',
          total: '25.00',
          lines: body.lines.map((line, index) => ({
            id: index + 1,
            ...line,
            line_total: '25.00',
            received_qty: '0.000',
          })),
        };
        savedOrders.push(order);
        return Promise.resolve(order);
      }
      if (path.startsWith('/api/v1/purchase/orders?')) return Promise.resolve(savedOrders);
      return Promise.resolve(null);
    });
  });

  it('saves a purchase order draft and refreshes its history', async () => {
    render(<PurchaseOrdersPage />);

    await screen.findByRole('heading', { name: 'New purchase order draft' });
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
      target: { value: '2.500' },
    });
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Unit price 1' }), {
      target: { value: '10.00' },
    });

    fireEvent.click(screen.getByRole('button', { name: 'Save draft' }));

    await screen.findByText('PO-20260001');
    expect(mocks.apiRequest).toHaveBeenCalledWith(
      '/api/v1/purchase/orders',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"qty":"2.500"'),
      }),
    );
    await waitFor(() => {
      expect(mocks.apiRequest).toHaveBeenCalledWith('/api/v1/purchase/orders?offset=0&limit=51');
    });
  });
});
