import { fireEvent, render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  apiRequest: vi.fn(),
  print: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useParams: () => ({ id: '9' }),
}));

vi.mock('@/components/auth/protected-page', () => ({
  ProtectedPage: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock('@/lib/auth-api', () => ({
  apiRequest: mocks.apiRequest,
  getApiUrl: (path: string) => `http://localhost:8000${path}`,
}));

import SalesInvoicePrintPage from './page';

describe('SalesInvoicePrintPage', () => {
  beforeEach(() => {
    mocks.apiRequest.mockReset();
    mocks.print.mockReset();
    Object.defineProperty(window, 'print', {
      configurable: true,
      value: mocks.print,
    });
    mocks.apiRequest.mockResolvedValue({
      company: {
        company_name: 'Sabuj Pran Ltd.',
        company_logo_path: '/brand/company-logo.svg',
        address: 'Dhaka',
        phone: '+8801000000000',
        email: 'accounts@example.com',
        currency_code: 'BDT',
        footer: 'Thank you for your business.',
      },
      invoice_no: 'INV-20260001',
      invoice_date: '2026-10-25',
      due_date: '2026-11-05',
      delivery_no: 'DN-20260001',
      order_no: 'SO-20260001',
      customer: {
        code: 'CUS-001',
        name: 'Acme Stores',
        mobile: '+8801000000001',
        email: 'buyer@example.com',
        address: 'Chattogram',
      },
      lines: [
        {
          product_sku: 'SKU-001',
          product_name: 'Finished Product',
          unit_code: 'pc',
          qty: '3.000',
          unit_price: '5.00',
          line_total: '15.00',
        },
      ],
      subtotal: '15.00',
      discount: '0.60',
      total: '14.40',
    });
  });

  it('loads readable invoice details and opens the browser print dialog', async () => {
    render(<SalesInvoicePrintPage />);

    expect(await screen.findByRole('heading', { name: 'Sales Invoice' })).toBeInTheDocument();
    expect(screen.getByText('Acme Stores')).toBeInTheDocument();
    expect(screen.getByText('Finished Product')).toBeInTheDocument();
    expect(screen.getByText('BDT 14.40')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Print / Save as PDF' }));

    expect(mocks.apiRequest).toHaveBeenCalledWith('/api/v1/sales/invoices/9/print');
    expect(mocks.print).toHaveBeenCalledOnce();
  });
});
