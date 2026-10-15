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
    permissions: ['sales.orders.read', 'sales.orders.create', 'sales.orders.update'],
  }),
}));

vi.mock('@/lib/auth-api', () => ({
  apiRequest: mocks.apiRequest,
}));

vi.mock('@/lib/notifications', () => ({
  showErrorToast: vi.fn(),
  showSuccessToast: vi.fn(),
}));

import SalesOrdersPage from './page';

describe('SalesOrdersPage', () => {
  beforeEach(() => {
    mocks.apiRequest.mockReset();
    const savedOrders: Record<string, unknown>[] = [];
    mocks.apiRequest.mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/v1/sales/orders/options') {
        return Promise.resolve({
          customers: [{ id: 2, code: 'CUS-1', name: 'Customer One' }],
          warehouses: [{ id: 3, code: 'MAIN', name: 'Main Warehouse' }],
          products: [{ id: 7, sku: 'FG-001', name: 'Finished Good', unit_code: 'pcs' }],
        });
      }
      if (init?.method === 'POST') {
        const body = JSON.parse(String(init.body)) as {
          doc_date: string;
          customer_id: number;
          warehouse_id: number;
          delivery_date: string | null;
          discount: string;
          note: string;
          lines: { product_id: number; qty_ordered: string; unit_price: string }[];
        };
        const order = {
          id: 11,
          doc_no: 'SO-20260001',
          ...body,
          quotation_id: null,
          status: 'DRAFT',
          subtotal: '25.00',
          total: '25.00',
          lines: body.lines.map((line, index) => ({
            id: index + 1,
            ...line,
            line_total: '25.00',
            qty_reserved: '0.000',
            qty_produced: '0.000',
            qty_delivered: '0.000',
          })),
        };
        savedOrders.push(order);
        return Promise.resolve(order);
      }
      if (path.startsWith('/api/v1/sales/orders?')) return Promise.resolve(savedOrders);
      return Promise.resolve(null);
    });
  });

  it('saves a sales order draft and refreshes its history', async () => {
    render(<SalesOrdersPage />);

    await screen.findByRole('heading', { name: 'New Sales Order' });
    fireEvent.change(screen.getByRole('combobox', { name: 'Customer' }), {
      target: { value: '2' },
    });
    fireEvent.change(screen.getByRole('combobox', { name: 'Warehouse' }), {
      target: { value: '3' },
    });
    fireEvent.change(screen.getByRole('combobox', { name: 'Product 1' }), {
      target: { value: '7' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: 'Quantity 1' }), {
      target: { value: '2.500' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: 'Unit price 1' }), {
      target: { value: '10.00' },
    });

    fireEvent.click(screen.getByRole('button', { name: 'Save Draft' }));

    await screen.findByText('SO-20260001');
    expect(mocks.apiRequest).toHaveBeenCalledWith(
      '/api/v1/sales/orders',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"qty_ordered":"2.500"'),
      }),
    );
    await waitFor(() => {
      expect(mocks.apiRequest).toHaveBeenCalledWith('/api/v1/sales/orders?offset=0&limit=51');
    });
  });
});
