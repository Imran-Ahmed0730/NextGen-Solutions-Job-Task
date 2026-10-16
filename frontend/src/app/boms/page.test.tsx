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
    permissions: [
      'production.boms.read',
      'production.boms.create',
      'production.boms.update',
      'production.boms.delete',
    ],
  }),
}));

vi.mock('@/lib/auth-api', () => ({
  apiRequest: mocks.apiRequest,
}));

vi.mock('@/lib/notifications', () => ({
  showErrorToast: mocks.showErrorToast,
  showSuccessToast: mocks.showSuccessToast,
}));

import BOMsPage from './page';

describe('BOMsPage', () => {
  beforeEach(() => {
    mocks.apiRequest.mockReset();
    mocks.showErrorToast.mockReset();
    mocks.showSuccessToast.mockReset();
    mocks.apiRequest.mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/v1/production/boms/options') {
        return Promise.resolve({
          raw_products: [
            { id: 1, sku: 'RAW-01', name: 'Flour', unit_code: 'kg', type: 'RAW' },
          ],
          finished_products: [
            { id: 2, sku: 'FG-01', name: 'Bread', unit_code: 'pc', type: 'FINISHED' },
          ],
        });
      }
      if (path.startsWith('/api/v1/production/boms?') || path === '/api/v1/production/boms') {
        if (init?.method === 'POST') {
          return Promise.resolve({
            id: 3,
            code: 'BOM-BREAD',
            finished_product_id: 2,
            output_qty: '10.000',
            labor_cost_default: '2.00',
            overhead_cost_default: '1.00',
            is_active: true,
            deleted_at: null,
            lines: [{ id: 4, raw_product_id: 1, qty: '3.000' }],
          });
        }
        return Promise.resolve([]);
      }
      return Promise.resolve(null);
    });
  });

  it('creates a BOM with its finished good, output quantity, and raw material line', async () => {
    render(<BOMsPage />);

    await screen.findByRole('heading', { name: 'Bills of Materials' });
    fireEvent.change(screen.getByRole('textbox', { name: 'BOM code' }), {
      target: { value: 'BOM-BREAD' },
    });
    fireEvent.change(screen.getByRole('combobox', { name: 'Finished product' }), {
      target: { value: '2' },
    });
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Output quantity' }), {
      target: { value: '10.000' },
    });
    fireEvent.change(screen.getByRole('combobox', { name: 'Raw material 1' }), {
      target: { value: '1' },
    });
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Quantity' }), {
      target: { value: '3.000' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create BOM' }));

    await waitFor(() =>
      expect(mocks.apiRequest).toHaveBeenCalledWith(
        '/api/v1/production/boms',
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"raw_product_id":1'),
        }),
      ),
    );
    expect(mocks.showSuccessToast).toHaveBeenCalledWith('BOM created.');
  });
});
