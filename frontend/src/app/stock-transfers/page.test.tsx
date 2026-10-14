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
    permissions: ['inventory.transfers.read', 'inventory.transfers.create'],
  }),
}));

vi.mock('@/lib/auth-api', () => ({
  apiRequest: mocks.apiRequest,
}));

vi.mock('@/lib/notifications', () => ({
  showErrorToast: vi.fn(),
  showSuccessToast: vi.fn(),
}));

import StockTransfersPage from './page';

describe('StockTransfersPage', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/');
    mocks.apiRequest.mockReset();
    let storedTransfer: {
      id: number;
      doc_no: string;
      doc_date: string;
      from_warehouse_id: number;
      to_warehouse_id: number;
      status: string;
      note: string | null;
      lines: { id: number; product_id: number; qty: string }[];
    } | null = null;
    mocks.apiRequest.mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/v1/inventory/transfers/options') {
        return Promise.resolve({
          warehouses: [
            { id: 1, code: 'MAIN', name: 'Main Warehouse' },
            { id: 2, code: 'REMOTE', name: 'Remote Warehouse' },
          ],
          products: [
            {
              id: 7,
              sku: 'RAW-001',
              name: 'Raw Material',
              unit_code: 'kg',
              is_stocked: true,
            },
          ],
        });
      }
      if (init?.method === 'POST') {
        storedTransfer = {
          id: 9,
          doc_no: 'TR-20260001',
          doc_date: '2026-10-14',
          from_warehouse_id: 1,
          to_warehouse_id: 2,
          status: 'POSTED',
          note: null,
          lines: [{ id: 3, product_id: 7, qty: '2.500' }],
        };
        return Promise.resolve(storedTransfer);
      }
      if (path === '/api/v1/inventory/transfers/9') {
        return Promise.resolve({
          id: 9,
          doc_no: 'TR-20260001',
          doc_date: '2026-10-14',
          from_warehouse_id: 1,
          to_warehouse_id: 2,
          status: 'POSTED',
          note: null,
          lines: [{ id: 3, product_id: 7, qty: '2.500' }],
        });
      }
      if (path.startsWith('/api/v1/inventory/transfers')) {
        return Promise.resolve(storedTransfer ? [storedTransfer] : []);
      }
      return Promise.resolve([]);
    });
  });

  it('posts a transfer and refreshes the transfer list', async () => {
    render(<StockTransfersPage />);

    await screen.findByRole('heading', { name: 'New transfer' });
    fireEvent.change(screen.getByRole('combobox', { name: 'From warehouse' }), {
      target: { value: '1' },
    });
    fireEvent.change(screen.getByRole('combobox', { name: 'To warehouse' }), {
      target: { value: '2' },
    });
    fireEvent.change(screen.getByRole('combobox', { name: 'Product 1' }), {
      target: { value: '7' },
    });
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Quantity 1' }), {
      target: { value: '2.500' },
    });
    expect(screen.getByRole('combobox', { name: 'From warehouse' })).toHaveValue(
      'Main Warehouse (MAIN)',
    );
    expect(screen.getByRole('combobox', { name: 'To warehouse' })).toHaveValue(
      'Remote Warehouse (REMOTE)',
    );
    expect(screen.getByRole('combobox', { name: 'Product 1' })).toHaveValue(
      'Raw Material (RAW-001)',
    );
    expect(screen.getByRole('spinbutton', { name: 'Quantity 1' })).toHaveValue(2.5);
    const form = screen.getByRole('heading', { name: 'New transfer' }).closest('form');
    expect(form).not.toBeNull();
    fireEvent.submit(form!);

    await screen.findByText('TR-20260001');
    expect(mocks.apiRequest).toHaveBeenCalledWith(
      '/api/v1/inventory/transfers',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"qty":"2.500"'),
      }),
    );
    await waitFor(() => {
      expect(mocks.apiRequest).toHaveBeenCalledWith(
        '/api/v1/inventory/transfers?offset=0&limit=50',
      );
    });
  });

  it('excludes the source warehouse from the destination options', async () => {
    render(<StockTransfersPage />);
    await screen.findByRole('heading', { name: 'New transfer' });
    fireEvent.change(screen.getByRole('combobox', { name: 'From warehouse' }), {
      target: { value: '1' },
    });
    fireEvent.focus(screen.getByRole('combobox', { name: 'To warehouse' }));
    await waitFor(() => {
      expect(screen.queryByRole('option', { name: /Main Warehouse/ })).not.toBeInTheDocument();
    });
  });

  it('loads a transfer linked from the stock ledger', async () => {
    window.history.replaceState({}, '', '/stock-transfers?document_id=9');
    render(<StockTransfersPage />);

    expect(await screen.findByText('Linked transfer: TR-20260001')).toBeInTheDocument();
    expect(mocks.apiRequest).toHaveBeenCalledWith('/api/v1/inventory/transfers/9');
  });
});
