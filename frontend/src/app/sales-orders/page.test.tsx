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
    permissions: [
      'sales.orders.read',
      'sales.orders.create',
      'sales.orders.update',
      'sales.orders.reserve',
      'sales.deliveries.create',
    ],
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
          products: [
            { id: 7, sku: 'FG-001', name: 'Finished Good', unit_code: 'pcs', allow_decimal: true },
          ],
        });
      }
      if (path.endsWith('/deliveries') && init?.method === 'POST') {
        const current = savedOrders[0] as {
          id: number;
          lines: { id: number; qty_delivered: string }[];
          deliveries: Record<string, unknown>[];
        };
        const body = JSON.parse(String(init.body)) as {
          doc_date: string;
          lines: { order_line_id: number; qty: string }[];
        };
        const delivery = {
          id: 101,
          doc_no: 'DEL-20260001',
          doc_date: body.doc_date,
          status: 'POSTED',
          lines: body.lines.map((line, index) => ({
            id: index + 1,
            ...line,
            product_id: 7,
            unit_cost_cogs: '4.2500',
          })),
        };
        savedOrders[0] = {
          ...current,
          lines: current.lines.map((line) => ({
            ...line,
            qty_delivered:
              body.lines.find((deliveryLine) => deliveryLine.order_line_id === line.id)?.qty ??
              line.qty_delivered,
          })),
          deliveries: [...current.deliveries, delivery],
        };
        return Promise.resolve(delivery);
      }
      if (path.includes('/reservations') && init?.method === 'POST') {
        const current = savedOrders[0] as {
          id: number;
          lines: {
            id: number;
            qty_reserved: string;
            reservations: {
              id: number;
              qty: string;
              qty_consumed: string;
              qty_released: string;
              status: string;
            }[];
          }[];
        };
        const updated = {
          ...current,
          lines: current.lines.map((line) => ({
            ...line,
            qty_available: '9.000',
            qty_reserved: '1.000',
            reservations: [
              ...line.reservations,
              {
                id: 91,
                qty: '1.000',
                qty_consumed: '0.000',
                qty_released: '0.000',
                status: 'ACTIVE',
              },
            ],
          })),
        };
        savedOrders[0] = updated;
        return Promise.resolve(updated);
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
          deliveries: [],
          lines: body.lines.map((line, index) => ({
            id: index + 1,
            ...line,
            line_total: '25.00',
            qty_reserved: '0.000',
            qty_produced: '0.000',
            qty_delivered: '0.000',
            qty_available: '10.000',
            qty_remaining: line.qty_ordered,
            reservations: [],
          })),
        };
        savedOrders.push(order);
        return Promise.resolve(order);
      }
      if (path.startsWith('/api/v1/sales/orders?')) {
        return Promise.resolve(savedOrders);
      }
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
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Quantity 1' }), {
      target: { value: '2.500' },
    });
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Unit price 1' }), {
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
    fireEvent.click(screen.getByRole('button', { name: 'View' }));
    expect(
      await screen.findByText(/2\.500 \/ 10\.000 \/ 0\.000 \/ 0\.000 \/ 0\.000 \/ 2\.500/),
    ).toBeInTheDocument();
  });

  it('reserves stock through the Sales Order action', async () => {
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
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Quantity 1' }), {
      target: { value: '2.500' },
    });
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Unit price 1' }), {
      target: { value: '10.00' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save Draft' }));
    await screen.findByText('SO-20260001');

    fireEvent.click(screen.getByRole('button', { name: 'View' }));
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Reserve quantity for line 1' }), {
      target: { value: '1.000' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Reserve' }));

    await screen.findByText(/Reservation 91: ACTIVE/);
    expect(mocks.apiRequest).toHaveBeenCalledWith(
      '/api/v1/sales/orders/11/lines/1/reservations',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ qty: '1.000' }),
      }),
    );
  });

  it('posts a delivery and displays stored COGS in delivery history', async () => {
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
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Quantity 1' }), {
      target: { value: '2.500' },
    });
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Unit price 1' }), {
      target: { value: '10.00' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save Draft' }));
    await screen.findByText('SO-20260001');

    fireEvent.click(screen.getByRole('button', { name: 'View' }));
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Delivery quantity for line 1' }), {
      target: { value: '1.500' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Post delivery' }));
    await waitFor(() => expect(mocks.apiRequest).toHaveBeenCalledTimes(8));

    expect(mocks.apiRequest).toHaveBeenCalledWith(
      '/api/v1/sales/orders/11/deliveries',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"qty":"1.500"'),
      }),
    );
    expect(await screen.findByText(/DEL-20260001/)).toBeInTheDocument();
    expect(screen.getByText(/COGS\/unit 4\.2500/)).toBeInTheDocument();
  });
});
