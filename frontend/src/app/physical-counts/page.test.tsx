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
    permissions: ['inventory.physical_counts.read', 'inventory.physical_counts.create'],
  }),
}));

vi.mock('@/lib/auth-api', () => ({
  apiRequest: mocks.apiRequest,
}));

vi.mock('@/lib/notifications', () => ({
  showErrorToast: vi.fn(),
  showSuccessToast: vi.fn(),
}));

import PhysicalCountsPage from './page';

describe('PhysicalCountsPage', () => {
  beforeEach(() => {
    mocks.apiRequest.mockReset();
    let count: {
      id: number;
      doc_no: string | null;
      count_date: string;
      warehouse_id: number;
      status: 'OPEN' | 'COUNTED' | 'POSTED';
      lines: {
        id: number;
        product_id: number;
        product_sku: string;
        product_name: string;
        unit_code: string;
        system_qty: string;
        counted_qty: string | null;
        variance_qty: string | null;
      }[];
    } | null = null;

    mocks.apiRequest.mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/v1/inventory/physical-counts/options') {
        return Promise.resolve([{ id: 1, code: 'MAIN', name: 'Main Warehouse' }]);
      }
      if (path === '/api/v1/inventory/physical-counts' && init?.method === 'POST') {
        count = {
          id: 9,
          doc_no: null,
          count_date: '2026-10-14',
          warehouse_id: 1,
          status: 'OPEN',
          lines: [
            {
              id: 1,
              product_id: 7,
              product_sku: 'RAW-001',
              product_name: 'Raw Material',
              unit_code: 'kg',
              system_qty: '5.000',
              counted_qty: null,
              variance_qty: null,
            },
            {
              id: 2,
              product_id: 8,
              product_sku: 'RAW-002',
              product_name: 'Second Material',
              unit_code: 'kg',
              system_qty: '0.000',
              counted_qty: null,
              variance_qty: null,
            },
          ],
        };
        return Promise.resolve(count);
      }
      if (path.endsWith('/lines') && init?.method === 'PUT' && count) {
        const body = JSON.parse(String(init.body)) as {
          lines: { product_id: number; counted_qty: string }[];
        };
        count.lines = count.lines.map((line) => {
          const updated = body.lines.find((item) => item.product_id === line.product_id);
          return updated
            ? {
                ...line,
                counted_qty: updated.counted_qty,
                variance_qty: (
                  Number(updated.counted_qty) - Number(line.system_qty)
                ).toFixed(3),
              }
            : line;
        });
        count.status = count.lines.every((line) => line.counted_qty !== null)
          ? 'COUNTED'
          : 'OPEN';
        return Promise.resolve(count);
      }
      if (path.endsWith('/post') && init?.method === 'POST' && count) {
        count = { ...count, doc_no: 'PC-20260001', status: 'POSTED' };
        return Promise.resolve(count);
      }
      if (path === '/api/v1/inventory/physical-counts/9' && count) {
        return Promise.resolve(count);
      }
      if (path.startsWith('/api/v1/inventory/physical-counts?')) {
        return Promise.resolve(
          count
            ? [
                {
                  id: count.id,
                  doc_no: count.doc_no,
                  count_date: count.count_date,
                  warehouse_id: count.warehouse_id,
                  status: count.status,
                  total_lines: count.lines.length,
                  counted_lines: count.lines.filter((line) => line.counted_qty !== null).length,
                },
              ]
            : [],
        );
      }
      return Promise.resolve([]);
    });
  });

  it('starts a snapshot, records quantities, reviews variances and posts it', async () => {
    render(<PhysicalCountsPage />);

    await screen.findByRole('heading', { name: 'Start a count sheet' });
    fireEvent.change(screen.getByRole('combobox', { name: 'Warehouse' }), {
      target: { value: '1' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Start count' }));

    await screen.findByText('Raw Material');
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Counted quantity RAW-001' }), {
      target: { value: '4.000' },
    });
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Counted quantity RAW-002' }), {
      target: { value: '0.000' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save counted quantities' }));

    await screen.findByRole('button', { name: 'Post count' });
    expect(screen.getByText('-1.000')).toBeInTheDocument();
    expect(mocks.apiRequest).toHaveBeenCalledWith(
      '/api/v1/inventory/physical-counts/9/lines',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({
          lines: [
            { product_id: 7, counted_qty: '4.000' },
            { product_id: 8, counted_qty: '0.000' },
          ],
        }),
      }),
    );

    fireEvent.click(screen.getByRole('button', { name: 'Post count' }));
    await screen.findByText('PC-20260001');
    expect(
      await screen.findByRole('spinbutton', { name: 'Counted quantity RAW-001' }),
    ).toBeDisabled();
    await waitFor(() => {
      expect(mocks.apiRequest).toHaveBeenCalledWith(
        '/api/v1/inventory/physical-counts/9/post',
        expect.objectContaining({ method: 'POST' }),
      );
    });
  });

  it('requires at least one quantity before saving', async () => {
    render(<PhysicalCountsPage />);
    fireEvent.change(await screen.findByRole('combobox', { name: 'Warehouse' }), {
      target: { value: '1' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Start count' }));
    await screen.findByText('Raw Material');
    fireEvent.click(screen.getByRole('button', { name: 'Save counted quantities' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Enter at least one counted quantity',
    );
    expect(
      mocks.apiRequest.mock.calls.some(([, init]) => init?.method === 'PUT'),
    ).toBe(false);
  });
});
