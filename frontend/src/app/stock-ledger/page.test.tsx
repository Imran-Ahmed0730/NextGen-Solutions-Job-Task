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
  useSessionProfile: () => ({ permissions: ['inventory.stock.read'] }),
}));

vi.mock('@/lib/auth-api', () => ({
  apiRequest: mocks.apiRequest,
}));

vi.mock('@/lib/notifications', () => ({
  showErrorToast: vi.fn(),
}));

import StockLedgerPage from './page';

describe('StockLedgerPage', () => {
  beforeEach(() => {
    mocks.apiRequest.mockReset();
    mocks.apiRequest.mockImplementation((path: string) => {
      if (path === '/api/v1/inventory/ledger/options') {
        return Promise.resolve({
          products: [{ id: 1, sku: 'RAW-001', name: 'Raw Material', unit_code: 'kg' }],
          warehouses: [{ id: 2, code: 'MAIN', name: 'Main Warehouse' }],
        });
      }
      return Promise.resolve([
        {
          id: 12,
          txn_date: '2026-10-14T00:00:00Z',
          product_id: 1,
          warehouse_id: 2,
          movement_type: 'TRANSFER_IN',
          qty_signed: '3.000',
          unit_cost: '4.0000',
          source_type: 'STOCK_TRANSFER',
          source_id: 9,
          source_line_id: 5,
          note: 'Warehouse move',
          running_qty: '8.000',
        },
      ]);
    });
  });

  it('filters movements and shows running balance and linked source document', async () => {
    render(<StockLedgerPage />);
    await screen.findByRole('option', { name: /Raw Material/ });

    fireEvent.change(screen.getByRole('combobox', { name: 'Product' }), {
      target: { value: '1' },
    });
    fireEvent.change(screen.getByRole('combobox', { name: 'Warehouse' }), {
      target: { value: '2' },
    });
    fireEvent.change(screen.getByLabelText('From date'), {
      target: { value: '2026-10-13' },
    });
    fireEvent.change(screen.getByLabelText('To date'), {
      target: { value: '2026-10-14' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    expect(await screen.findByText('TRANSFER_IN')).toBeInTheDocument();
    expect(screen.getByText('8.000')).toBeInTheDocument();
    const sourceLink = screen.getByRole('link', { name: 'STOCK_TRANSFER #9' });
    expect(sourceLink).toHaveAttribute('href', '/stock-transfers?document_id=9');
    await waitFor(() => {
      expect(mocks.apiRequest).toHaveBeenCalledWith(
        expect.stringContaining(
          'product_id=1&offset=0&limit=50&warehouse_id=2&date_from=2026-10-13&date_to=2026-10-14',
        ),
      );
    });
    expect(within(screen.getByRole('table')).getByText('Warehouse move')).toBeInTheDocument();
  });

  it('requires a product before requesting ledger history', async () => {
    render(<StockLedgerPage />);
    await screen.findByRole('option', { name: /Raw Material/ });
    const form = screen.getByRole('button', { name: 'Search' }).closest('form');
    expect(form).not.toBeNull();
    fireEvent.submit(form!);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Choose a product to view its stock ledger.',
    );
    expect(
      mocks.apiRequest.mock.calls.some(([path]) => path.startsWith('/api/v1/inventory/ledger?')),
    ).toBe(false);
  });
});
