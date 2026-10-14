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
  useSessionProfile: () => ({ permissions: ['inventory.stock.read'] }),
}));

vi.mock('@/lib/auth-api', () => ({
  apiRequest: mocks.apiRequest,
}));

vi.mock('@/lib/notifications', () => ({
  showErrorToast: vi.fn(),
}));

import WarehouseStockPage from './page';

describe('WarehouseStockPage', () => {
  beforeEach(() => {
    mocks.apiRequest.mockReset();
    mocks.apiRequest.mockImplementation((path: string) => {
      if (path.startsWith('/api/v1/warehouses')) {
        return Promise.resolve([
          { id: 1, code: 'MAIN', name: 'Main Warehouse' },
          { id: 2, code: 'REMOTE', name: 'Remote Warehouse' },
        ]);
      }
      return Promise.resolve([
        {
          product_id: 7,
          product_sku: 'RAW-001',
          product_name: 'Raw Material',
          unit_code: 'kg',
          warehouse_id: 1,
          warehouse_code: 'MAIN',
          warehouse_name: 'Main Warehouse',
          qty_on_hand: '12.500',
          qty_reserved: '2.000',
          available: '10.500',
        },
      ]);
    });
  });

  it('shows warehouse quantities and applies warehouse/product filters', async () => {
    render(<WarehouseStockPage />);

    expect(await screen.findByText('Raw Material')).toBeInTheDocument();
    expect(screen.getByText('RAW-001')).toBeInTheDocument();
    expect(screen.getByText('10.5')).toBeInTheDocument();

    fireEvent.change(screen.getByRole('combobox', { name: /warehouse/i }), {
      target: { value: '2' },
    });
    fireEvent.change(screen.getByPlaceholderText(/search by product name or sku/i), {
      target: { value: 'RAW' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    await waitFor(() => {
      expect(mocks.apiRequest).toHaveBeenCalledWith(
        expect.stringContaining('warehouse_id=2'),
      );
      expect(mocks.apiRequest).toHaveBeenCalledWith(
        expect.stringContaining('search=RAW'),
      );
    });
  });
});
