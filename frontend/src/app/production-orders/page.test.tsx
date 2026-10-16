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
    permissions: ['production.orders.read', 'production.orders.create', 'production.orders.update'],
  }),
}));

vi.mock('@/lib/auth-api', () => ({
  apiRequest: mocks.apiRequest,
}));

vi.mock('@/lib/notifications', () => ({
  showErrorToast: mocks.showErrorToast,
  showSuccessToast: mocks.showSuccessToast,
}));

import ProductionOrdersPage from './page';

describe('ProductionOrdersPage', () => {
  beforeEach(() => {
    mocks.apiRequest.mockReset();
    mocks.showErrorToast.mockReset();
    mocks.showSuccessToast.mockReset();
    let order: Record<string, unknown> | null = null;
    mocks.apiRequest.mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/v1/production/orders/options') {
        return Promise.resolve({
          boms: [{
            id: 2,
            code: 'BOM-BREAD',
            finished_product_id: 3,
            output_qty: '10.000',
            labor_cost_default: '2.00',
            overhead_cost_default: '1.50',
          }],
          warehouses: [{ id: 4, code: 'MAIN', name: 'Main Warehouse' }],
          sales_order_lines: [{
            id: 6,
            sales_order_id: 10,
            doc_no: 'SO-20260001',
            product_id: 3,
            product_sku: 'FG-03',
            product_name: 'Bread',
            warehouse_id: 4,
            qty_ordered: '10.000',
            qty_reserved: '0.000',
            qty_produced: '0.000',
            qty_delivered: '0.000',
          }],
        });
      }
      if (path === '/api/v1/production/orders' && init?.method === 'POST') {
        const body = JSON.parse(String(init.body)) as Record<string, unknown>;
        order = {
          id: 5,
          doc_no: 'PO-20260001',
          ...body,
          finished_product_id: 3,
          actual_qty: null,
          status: 'DRAFT',
          labor_cost: null,
          overhead_cost: null,
          material_cost: null,
          total_cost: null,
          unit_cost: null,
          consumption: [],
          outputs: [],
        };
        return Promise.resolve(order);
      }
      if (path === '/api/v1/production/orders/5/start') {
        order = { ...order, status: 'IN_PROGRESS' };
        return Promise.resolve(order);
      }
      if (path === '/api/v1/production/orders/5/complete') {
        const body = JSON.parse(String(init?.body)) as {
          actual_qty: string;
          labor_cost: string;
          overhead_cost: string;
        };
        order = {
          ...order,
          ...body,
          actual_qty: body.actual_qty,
          status: 'COMPLETED',
          material_cost: '2.50',
          total_cost: '6.00',
          unit_cost: '1.2000',
          consumption: [{ id: 8, product_id: 1, qty: '1.250', unit_cost: '2.0000', line_cost: '2.50' }],
          outputs: [{ id: 9, product_id: 3, qty: body.actual_qty, unit_cost: '1.2000' }],
        };
        return Promise.resolve(order);
      }
      if (path === '/api/v1/production/orders') return Promise.resolve(order ? [order] : []);
      return Promise.resolve(null);
    });
  });

  it('creates, starts, and completes a production order with actual costs', async () => {
    render(<ProductionOrdersPage />);
    await screen.findByRole('heading', { name: 'Production Orders' });

    fireEvent.change(screen.getByRole('combobox', { name: 'BOM' }), {
      target: { value: '2' },
    });
    fireEvent.change(screen.getByRole('combobox', { name: 'Sales Order line' }), {
      target: { value: '6' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: 'Planned quantity' }), {
      target: { value: '4.000' },
    });
    fireEvent.change(screen.getByRole('combobox', { name: 'Warehouse' }), {
      target: { value: '4' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create Production Order' }));

    await screen.findByText('PO-20260001');
    expect(mocks.apiRequest).toHaveBeenCalledWith(
      '/api/v1/production/orders',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringMatching(
          /"sales_order_line_id":6.*"planned_qty":"4\.000"/,
        ),
      }),
    );

    fireEvent.click(screen.getByRole('button', { name: 'Start' }));
    await screen.findByText('IN PROGRESS');
    fireEvent.click(screen.getByRole('button', { name: 'Complete' }));
    fireEvent.change(screen.getByRole('textbox', { name: 'Actual output quantity' }), {
      target: { value: '5.000' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Post production' }));

    await screen.findByText('COMPLETED');
    expect(mocks.apiRequest).toHaveBeenCalledWith(
      '/api/v1/production/orders/5/complete',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          actual_qty: '5.000',
          labor_cost: '2.00',
          overhead_cost: '1.50',
        }),
      }),
    );

    fireEvent.click(screen.getByRole('button', { name: 'Details' }));
    await waitFor(() => expect(screen.getByText(/Total: 6\.00/)).toBeInTheDocument());
  });
});
