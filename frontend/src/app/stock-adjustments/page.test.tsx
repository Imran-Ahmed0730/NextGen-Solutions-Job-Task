import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
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
    permissions: ['inventory.adjustments.read', 'inventory.adjustments.create'],
  }),
}));

vi.mock('@/lib/auth-api', () => ({
  apiRequest: mocks.apiRequest,
}));

vi.mock('@/lib/notifications', () => ({
  showErrorToast: vi.fn(),
  showSuccessToast: vi.fn(),
}));

import StockAdjustmentsPage from './page';

describe('StockAdjustmentsPage', () => {
  beforeEach(() => {
    mocks.apiRequest.mockReset();
    let storedAdjustment: {
      id: number;
      doc_no: string;
      doc_date: string;
      warehouse_id: number;
      reason: string;
      status: string;
      lines: { id: number; product_id: number; qty_signed: string; unit_cost: string }[];
    } | null = null;
    mocks.apiRequest.mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/v1/inventory/adjustments/options') {
        return Promise.resolve({
          warehouses: [{ id: 1, code: 'MAIN', name: 'Main Warehouse' }],
          products: [
            {
              id: 7,
              sku: 'RAW-001',
              name: 'Raw Material',
              unit_code: 'kg',
              is_stocked: true,
            },
            {
              id: 8,
              sku: 'TRD-001',
              name: 'Non-stocked Product',
              unit_code: 'ea',
              is_stocked: false,
            },
          ],
        });
      }
      if (init?.method === 'POST') {
        storedAdjustment = {
          id: 9,
          doc_no: 'ADJ-20260001',
          doc_date: '2026-10-14',
          warehouse_id: 1,
          reason: 'Count correction',
          status: 'POSTED',
          lines: [{ id: 3, product_id: 7, qty_signed: '-2.500', unit_cost: '4.0000' }],
        };
        return Promise.resolve(storedAdjustment);
      }
      if (path.startsWith('/api/v1/inventory/adjustments')) {
        return Promise.resolve(storedAdjustment ? [storedAdjustment] : []);
      }
      return Promise.resolve([]);
    });
  });

  it('posts a signed adjustment and refreshes the adjustment list', async () => {
    render(<StockAdjustmentsPage />);

    await screen.findByRole('heading', { name: 'New adjustment' });
    await screen.findByRole('option', { name: /Raw Material/ });
    expect(screen.queryByRole('option', { name: /Non-stocked Product/ })).not.toBeInTheDocument();
    fireEvent.change(screen.getByRole('combobox', { name: 'Warehouse' }), {
      target: { value: '1' },
    });
    fireEvent.change(screen.getByRole('combobox', { name: 'Product 1' }), {
      target: { value: '7' },
    });
    fireEvent.change(screen.getByRole('combobox', { name: 'Direction 1' }), {
      target: { value: 'OUT' },
    });
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Quantity 1' }), {
      target: { value: '2.500' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: 'Adjustment reason' }), {
      target: { value: 'Count correction' },
    });
    const form = screen.getByRole('heading', { name: 'New adjustment' }).closest('form');
    expect(form).not.toBeNull();
    fireEvent.submit(form!);

    await screen.findByText('ADJ-20260001');
    expect(mocks.apiRequest).toHaveBeenCalledWith(
      '/api/v1/inventory/adjustments',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"qty_signed":"-2.500"'),
      }),
    );
    await waitFor(() => {
      expect(mocks.apiRequest).toHaveBeenCalledWith(
        '/api/v1/inventory/adjustments?offset=0&limit=50',
      );
    });
    expect(screen.getByText('Count correction')).toBeInTheDocument();
    expect(within(screen.getByRole('table')).getByText(/RAW-001 -2.500/)).toBeInTheDocument();
  });

  it('does not allow zero quantities to be posted', async () => {
    render(<StockAdjustmentsPage />);
    await screen.findByRole('heading', { name: 'New adjustment' });
    await screen.findByRole('option', { name: /Raw Material/ });
    fireEvent.change(screen.getByRole('combobox', { name: 'Warehouse' }), {
      target: { value: '1' },
    });
    fireEvent.change(screen.getByRole('combobox', { name: 'Product 1' }), {
      target: { value: '7' },
    });
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Quantity 1' }), {
      target: { value: '0' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: 'Adjustment reason' }), {
      target: { value: 'Zero test' },
    });
    const form = screen.getByRole('heading', { name: 'New adjustment' }).closest('form');
    expect(form).not.toBeNull();
    fireEvent.submit(form!);

    expect(await screen.findByRole('alert')).toHaveTextContent('Quantity must not be zero');
    expect(
      mocks.apiRequest.mock.calls.some(([, init]) => init?.method === 'POST'),
    ).toBe(false);
  });
});
